#!/usr/bin/env python3
import sys
import os
import json
import argparse
import pathlib
import time
import fcntl
import getpass
import signal
import re
import traceback

# 2026年エコシステムルールに基づき、structlogを適用
try:
    import structlog
except ImportError:
    # 仮想環境内で未インストール時のための簡易代替処理（通常はインストール済み前提）
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    class DummyStructlog:
        def get_logger(self):
            class Logger:
                def __init__(self):
                    self._kwargs = {}
                def bind(self, **kwargs):
                    self._kwargs.update(kwargs)
                    return self
                def info(self, event, **kwargs):
                    print(json.dumps({"level": "info", "event": event, **self._kwargs, **kwargs}), file=sys.stderr)
                def warning(self, event, **kwargs):
                    print(json.dumps({"level": "warning", "event": event, **self._kwargs, **kwargs}), file=sys.stderr)
                def error(self, event, **kwargs):
                    print(json.dumps({"level": "error", "event": event, **self._kwargs, **kwargs}), file=sys.stderr)
                def critical(self, event, **kwargs):
                    print(json.dumps({"level": "critical", "event": event, **self._kwargs, **kwargs}), file=sys.stderr)
                def debug(self, event, **kwargs):
                    print(json.dumps({"level": "debug", "event": event, **self._kwargs, **kwargs}), file=sys.stderr)
            return Logger()
    structlog = DummyStructlog()

# 大域変数およびシグナルハンドラ用
active_phase = "setup"
recursion_lock_file = None
recursion_lock_fd = None
checkpoint_path = None
allowed_scopes_global = []

# シークレットマスク用正規表現（簡易なAPIキー、シークレットトークンなどの検出）
SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|secret|password|token|auth|credential)["\'\s]*[:=]["\'\s]*([a-zA-Z0-9_\-\.\~]{8,})'),
]

def mask_secrets(text: str) -> str:
    """テキスト内に含まれる一般的なシークレット情報を [REDACTED] にマスクする"""
    if not text:
        return text
    # ユーザー名とAPP_DATA_DIRのマスク（仕様L8要件）
    user = getpass.getuser()
    if user:
        text = text.replace(user, "[USER]")
    
    app_data_dir = os.environ.get("APP_DATA_DIR")
    if app_data_dir:
        text = text.replace(app_data_dir, "[APP_DATA_DIR]")
        
    for pattern in SECRET_PATTERNS:
        def replace_match(match):
            key = match.group(1)
            val = match.group(2)
            # 8文字以上の英数字トークンをマスク
            return match.group(0).replace(val, "[REDACTED]")
        text = pattern.sub(replace_match, text)
    return text

def setup_structlog(debug_mode: bool):
    """structlogの標準化設定（ISO 8601ミリ秒精度タイムスタンプ、マスク処理プロセッサ）"""
    if hasattr(structlog, "configure"):
        def mask_processor(logger, name, event_dict):
            # ログ辞書内のすべての文字列値に対してシークレットマスクを適用
            for key, val in list(event_dict.items()):
                if isinstance(val, str):
                    event_dict[key] = mask_secrets(val)
                elif isinstance(val, dict):
                    event_dict[key] = {k: (mask_secrets(v) if isinstance(v, str) else v) for k, v in val.items()}
            return event_dict

        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso", utc=False),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                mask_processor,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(sys.stderr),
            wrapper_class=structlog.stdlib.BoundLogger if hasattr(structlog, "stdlib") else structlog.BoundLogger,
            cache_logger_on_first_use=True,
        )

logger = structlog.get_logger()

def get_allowed_scopes(args_scopes: str) -> list:
    """許可されたスコープディレクトリのリストを取得（デフォルトはプロジェクトルートと$APP_DATA_DIR）"""
    scopes = []
    
    # 環境変数または引数から取得
    env_scopes = os.environ.get("ALLOWED_SCOPES", "")
    scopes_str = args_scopes or env_scopes
    
    if scopes_str:
        for s in scopes_str.split(","):
            s = s.strip()
            if s:
                scopes.append(pathlib.Path(s).resolve(strict=False))
    else:
        # デフォルトスコープ（プロジェクトルートおよび$APP_DATA_DIR）
        scopes.append(pathlib.Path(os.getcwd()).resolve())
        app_data_dir = os.environ.get("APP_DATA_DIR")
        if app_data_dir:
            scopes.append(pathlib.Path(app_data_dir).resolve(strict=False))
        else:
            # $APP_DATA_DIRが未定義の場合はフォールバック
            scopes.append(pathlib.Path("/Users/ryota/.gemini/antigravity").resolve(strict=False))
            
    return scopes

def validate_path(path_str: str, allowed_scopes: list, read_only: bool = False) -> pathlib.Path:
    """パスが許可されたスコープ内にあるかを厳密に検証する（ディレクトリトラバーサル防止）"""
    p = pathlib.Path(path_str)
    
    # シンボリックリンクの解決
    try:
        resolved_path = p.resolve(strict=False)
    except Exception as e:
        raise ValueError(f"Path resolution failed: {path_str}. Error: {str(e)}")
        
    in_scope = False
    for scope in allowed_scopes:
        try:
            # 解決された絶対パスが許可された親パス配下にあるかを判定
            if resolved_path.parts[:len(scope.parts)] == scope.parts:
                in_scope = True
                break
        except Exception:
            continue
            
    if not in_scope:
        # セキュリティ違反ログ
        logger.error("SECURITY_VIOLATION_PATH_TRAVERSAL", 
                     requested_path=str(resolved_path), 
                     allowed_scopes=[str(s) for s in allowed_scopes])
        raise ValueError(f"Security violation: path '{path_str}' is outside allowed scopes.")
        
    # 読み取り専用ファイルの場合、シンボリックリンクのターゲット実体パスも検査
    if read_only and p.is_symlink():
        try:
            link_target = pathlib.Path(os.readlink(p)).resolve(strict=False)
            link_in_scope = False
            for scope in allowed_scopes:
                if link_target.parts[:len(scope.parts)] == scope.parts:
                    link_in_scope = True
                    break
            if not link_in_scope:
                logger.error("SECURITY_VIOLATION_PATH_TRAVERSAL", 
                             requested_path=str(link_target), 
                             allowed_scopes=[str(s) for s in allowed_scopes])
                raise ValueError(f"Security violation: symlink target '{str(link_target)}' is outside allowed scopes.")
        except Exception as e:
            raise ValueError(f"Symlink target validation failed: {str(e)}")

    return resolved_path

def check_recursion_guard(app_data_dir: str):
    """再帰呼び出しガード（環境変数および排他ロックファイルのチェックと更新）"""
    global recursion_lock_file, recursion_lock_fd
    
    # 1. 環境変数による深さ管理
    depth_env_name = "THEOREM_VERIFICATION_DEPTH"
    depth = 0
    depth_str = os.environ.get(depth_env_name)
    if depth_str:
        try:
            depth = int(depth_str)
        except ValueError:
            depth = 5  # 不正フォーマット時は異常系（Fail-safe）で上限値扱い
            
    if depth >= 5:
        logger.critical("RECURSION_GUARD_TRIGGERED", 
                        reason="Max recursion depth reached (Environment Variable)", 
                        current_depth=depth)
        # 異常終了時のリカバリメタデータ（HITLシグナル）
        lock_path_str = f"{app_data_dir}/scratch/execution_depth.lock"
        logger.error("HITL_RECOVERY_REQUIRED",
                     hitl_recovery_context={
                         "recovery_action": "REMOVE_LOCK_FILE",
                         "target_path": lock_path_str
                     })
        sys.exit(3)
        
    # 子プロセス呼び出し用の深度更新（環境変数）
    os.environ[depth_env_name] = str(depth + 1)
    
    # 2. 排他ロック・カウンタファイルによるガード
    lock_dir = pathlib.Path(app_data_dir) / "scratch"
    validate_path(str(lock_dir), allowed_scopes_global)
    lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    
    lock_path = lock_dir / "execution_depth.lock"
    recursion_lock_file = lock_path
    
    try:
        # 読み書きモードでオープン
        recursion_lock_fd = open(lock_path, "a+")
        
        # flockによるノンブロッキング排他ロック取得
        try:
            fcntl.flock(recursion_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # ロック獲得失敗時の生存確認ロジック
            # a+モードなので先頭へシークして読み取り
            recursion_lock_fd.seek(0)
            content = recursion_lock_fd.read().strip()
            
            pid = None
            mtime = None
            if content:
                try:
                    data = json.loads(content)
                    pid = data.get("pid")
                    mtime = data.get("timestamp")
                except Exception:
                    pass
            
            # 生存確認：PIDプロセスが存在しない、または5分以上経過
            stale = False
            if pid is not None:
                try:
                    os.kill(pid, 0)
                except OSError:
                    stale = True  # プロセスが存在しない
                    
            if mtime is not None and (time.time() - mtime > 300):
                stale = True  # 5分以上経過
                
            if stale or not content:
                # ロックファイルを強制リセット
                recursion_lock_fd.close()
                # ロックファイルを空にして開き直す
                recursion_lock_fd = open(lock_path, "w+")
                fcntl.flock(recursion_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                # 生存中の他プロセスが存在するため、競合・再帰制限超過と判定
                logger.critical("RECURSION_GUARD_TRIGGERED", 
                                reason="Active locks found on counter file (Parallel / Recursive)", 
                                lock_pid=pid)
                logger.error("HITL_RECOVERY_REQUIRED",
                             hitl_recovery_context={
                                 "recovery_action": "REMOVE_LOCK_FILE",
                                 "target_path": str(lock_path)
                             })
                sys.exit(3)
        
        # ロック獲得成功後のカウンタ更新
        recursion_lock_fd.seek(0)
        content = recursion_lock_fd.read().strip()
        
        counter = 0
        if content:
            try:
                data = json.loads(content)
                counter = int(data.get("counter", 0))
            except Exception:
                counter = 5  # パース失敗時は安全側に倒して上限扱い
                
        if counter < 0 or counter >= 5:
            logger.critical("RECURSION_GUARD_TRIGGERED", 
                            reason="Max recursion depth reached (Counter File)", 
                            current_counter=counter)
            logger.error("HITL_RECOVERY_REQUIRED",
                         hitl_recovery_context={
                             "recovery_action": "REMOVE_LOCK_FILE",
                             "target_path": str(lock_path)
                         })
            # ロックを解放して終了
            fcntl.flock(recursion_lock_fd, fcntl.LOCK_UN)
            recursion_lock_fd.close()
            try:
                lock_path.unlink()
            except Exception:
                pass
            sys.exit(3)
            
        # カウンタのインクリメントと保存
        new_data = {
            "counter": counter + 1,
            "pid": os.getpid(),
            "timestamp": time.time()
        }
        recursion_lock_fd.seek(0)
        recursion_lock_fd.truncate()
        recursion_lock_fd.write(json.dumps(new_data))
        recursion_lock_fd.flush()
        os.fsync(recursion_lock_fd.fileno())
        
        # 排他ロックはクローズ（終了時）まで保持し続ける (仕様L2/L6/L9要件)
        
    except Exception as e:
        logger.error("RECURSION_GUARD_INITIALIZATION_FAILED", error=str(e))
        sys.exit(1)

def release_recursion_guard():
    """再帰カウンタのデクリメントおよびロック解放（終了処理用）"""
    global recursion_lock_file, recursion_lock_fd
    if recursion_lock_fd is None or recursion_lock_fd.closed:
        return
        
    try:
        # 排他ロックが保持されている状態で処理を実行 (仕様L4/L6/L9要件)
        recursion_lock_fd.seek(0)
        content = recursion_lock_fd.read().strip()
        counter = 1
        if content:
            try:
                data = json.loads(content)
                counter = int(data.get("counter", 1))
            except Exception:
                pass
                
        if counter <= 1:
            # カウンタが1以下の場合はロックファイルを削除
            recursion_lock_fd.close()
            if recursion_lock_file and recursion_lock_file.exists():
                recursion_lock_file.unlink()
        else:
            # カウンタをデクリメントして保存
            new_data = {
                "counter": counter - 1,
                "pid": os.getpid(),
                "timestamp": time.time()
            }
            recursion_lock_fd.seek(0)
            recursion_lock_fd.truncate()
            recursion_lock_fd.write(json.dumps(new_data))
            recursion_lock_fd.flush()
            os.fsync(recursion_lock_fd.fileno())
            # クローズ時にOSレベルで自動ロック解放
            recursion_lock_fd.close()
    except Exception as e:
        logger.error("RECURSION_GUARD_RELEASE_FAILED", error=str(e))

def signal_handler(signum, frame):
    """外部中断シグナルのトラップとクリーンアップ"""
    global active_phase
    logger.error("PROCESS_INTERRUPTED", signal=signum, active_phase=active_phase)
    
    # ロックファイルの安全なデクリメント/削除
    release_recursion_guard()
    
    # 一時ファイルの削除（チェックポイントは保持）
    sys.exit(1)

def execute_atomic_write(target_path_str: str, content_data: str, is_json: bool = False):
    """所有者権限(0600)の確保、一時ファイル出力、バックアップ作成、EXDEVフォールバックを含むアトミック置換"""
    target = pathlib.Path(target_path_str)
    validate_path(str(target), allowed_scopes_global)
    
    # シンボリックリンク検査
    if target.exists() and target.is_symlink():
        raise ValueError(f"Security error: target path '{target_path_str}' is a symlink.")
        
    # ディレクトリ作成 (0700)
    parent = target.parent
    if not parent.exists():
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        
    # 一時ファイル作成
    tmp_path = target.with_suffix(".tmp")
    if tmp_path.exists():
        tmp_path.unlink()
        
    try:
        # 1. 一時ファイルへの書き出し (0600権限)
        # O_CREAT | O_WRONLY | O_TRUNC を用い、パーミッションを明示的に 0600 で作成
        fd = os.open(tmp_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(content_data)
            f.flush()
            os.fsync(f.fileno())
            
        # 2. バックアップの作成 (存在する場合)
        bak_path = target.with_suffix(".bak")
        if target.exists():
            if target.is_symlink():
                raise ValueError("Security error: target path is a symlink.")
            try:
                # ターゲットからバックアップパスへコピー（0600を適用）
                if bak_path.exists():
                    bak_path.unlink()
                # 読み込み
                with open(target, 'r') as src:
                    target_data = src.read()
                # バックアップ書き込み (0600)
                bak_fd = os.open(bak_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
                with os.fdopen(bak_fd, 'w') as bak_f:
                    bak_f.write(target_data)
                    bak_f.flush()
                    os.fsync(bak_f.fileno())
            except Exception as e:
                # バックアップ失敗時は一時ファイルを削除して異常終了
                if tmp_path.exists():
                    tmp_path.unlink()
                raise IOError(f"Failed to create backup file. Aborting replace. Error: {str(e)}")
                
        # 3. アトミックリネーム (EXDEVフォールバック対応)
        try:
            os.rename(tmp_path, target)
        except OSError as e:
            # デバイス境界を越えるエラー (EXDEV) 時のフォールバック (コピー & 削除)
            if e.errno == 18:  # EXDEV
                try:
                    # コピー書き込み (0600)
                    target_fd = os.open(target, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
                    with os.fdopen(target_fd, 'w') as dest:
                        dest.write(content_data)
                        dest.flush()
                        os.fsync(dest.fileno())
                    # 一時ファイルの削除
                    tmp_path.unlink()
                except Exception as copy_err:
                    # コピー失敗時のロールバック（書きかけターゲット削除、バックアップ復元、一時ファイル削除）
                    if target.exists():
                        target.unlink()
                    if bak_path.exists():
                        # バックアップから復元 (0600)
                        with open(bak_path, 'r') as bak_src:
                            bak_data = bak_src.read()
                        restore_fd = os.open(target, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
                        with os.fdopen(restore_fd, 'w') as restore_dest:
                            restore_dest.write(bak_data)
                            restore_dest.flush()
                            os.fsync(restore_dest.fileno())
                    if tmp_path.exists():
                        tmp_path.unlink()
                    raise IOError(f"EXDEV fallback write failed. Rollback executed. Error: {str(copy_err)}")
            else:
                # その他のOSエラー
                if tmp_path.exists():
                    tmp_path.unlink()
                raise e
    except Exception as e:
        logger.error("FILE_WRITE_FAILED", target_path=target_path_str, error=str(e))
        # 異常終了時のリカバリメタデータ（HITLシグナル）
        logger.error("HITL_RECOVERY_REQUIRED",
                     hitl_recovery_context={
                         "recovery_action": "RESTORE_BACKUP",
                         "target_path": target_path_str
                     })
        sys.exit(1)

def save_checkpoint(offset: int, processed_rows: int, metrics: dict, defects_mtime: float):
    """50,000行ごと、または中断時に、0600権限でチェックポイントをアトミックに永続化"""
    global checkpoint_path
    if not checkpoint_path:
        return
        
    checkpoint_data = {
        "file_mtime": defects_mtime,
        "offset": offset,
        "processed_rows": processed_rows,
        "metrics": metrics
    }
    
    # アトミックな書き込み（0600）
    execute_atomic_write(str(checkpoint_path), json.dumps(checkpoint_data))

def load_checkpoint(defects_mtime: float) -> dict:
    """有効なチェックポイントが存在すれば読み込み、整合性が取れていれば状態を復元"""
    global checkpoint_path
    if not checkpoint_path or not checkpoint_path.exists():
        return None
        
    try:
        with open(checkpoint_path, 'r') as f:
            data = json.loads(f.read())
        # ファイル更新日時の一致検証
        if data.get("file_mtime") == defects_mtime:
            logger.info("CHECKPOINT_RESTORED", 
                        offset=data.get("offset"), 
                        processed_rows=data.get("processed_rows"))
            return data
    except Exception as e:
        logger.warning("CHECKPOINT_LOAD_FAILED", error=str(e))
    return None

def main():
    global active_phase, checkpoint_path, allowed_scopes_global
    
    # シグナルハンドラ設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 実行環境ガード (仮想環境チェック)
    in_venv = os.environ.get("VIRTUAL_ENV") or (sys.prefix != sys.base_prefix)
    if not in_venv:
        # グローバルPython実行の防止
        print(json.dumps({
            "level": "error",
            "event": "GLOBAL_PYTHON_EXECUTION_PREVENTED",
            "message": "uv run verify_theorems.py を使用するか、仮想環境を有効化してください"
        }), file=sys.stderr)
        sys.exit(1)
        
    # 引数定義
    parser = argparse.ArgumentParser(description="定理検証プログラム (v9)")
    parser.add_argument("--targets", default="target_files.json", help="対象ファイルリスト (JSON)")
    parser.add_argument("--defects", default="", help="欠陥データファイル (JSONL)")
    parser.add_argument("--output", default="", help="Markdownレポート出力パス")
    parser.add_argument("--output-json", default="", help="JSONメタデータ出力パス")
    parser.add_argument("--workflow-context", default="", help="実行識別コンテキスト")
    parser.add_argument("--debug", action="store_true", help="デバッグログを有効化")
    parser.add_argument("--allowed-scopes", default="", help="許可スコープパス(カンマ区切り)")
    
    # 解析
    args = parser.parse_args()
    
    # structlogの設定
    setup_structlog(args.debug)
    
    # 1. SETUP フェーズの開始
    active_phase = "setup"
    logger.info("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="started")
    
    # 許可スコープの取得と検証
    allowed_scopes_global = get_allowed_scopes(args.allowed_scopes)
    
    # デフォルトのアプリデータ領域パス解決
    app_data_dir = os.environ.get("APP_DATA_DIR", "/Users/ryota/.gemini/antigravity")
    
    # パス引数の解決（デフォルト値の適用）
    defects_path_str = args.defects or f"{app_data_dir}/scratch/defects.jsonl"
    output_md_str = args.output or f"{app_data_dir}/scratch/theorem_verification_results.md"
    output_json_str = args.output_json or f"{app_data_dir}/scratch/theorem_verification_results.json"
    
    checkpoint_path = pathlib.Path(app_data_dir) / "scratch" / "verify_checkpoint.json.tmp"
    
    # 入力パラメータのバリデーション (L7/L3要件)
    # argparseのハイフンマッピング自動置換の解決
    context_val = getattr(args, "workflow_context", "")
    if context_val:
        if not re.match(r'^[a-zA-Z0-9\-\_\.]+$', context_val):
            logger.error("INVALID_INPUT_PARAMETER", parameter="workflow_context", value=context_val)
            sys.exit(1)
            
    # 再帰呼び出しガード
    check_recursion_guard(app_data_dir)
    
    # ターゲットファイルリストの読み込みとバリデーション
    targets_path = validate_path(args.targets, allowed_scopes_global, read_only=True)
    try:
        with open(targets_path, 'r') as f:
            targets_list = json.loads(f.read())
        if not isinstance(targets_list, list) or not all(isinstance(x, str) for x in targets_list):
            logger.error("INVALID_TARGETS_SCHEMA", error="target_files.json must be an array of file path strings")
            logger.error("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="failed", error_class="ValueError", error_message="Invalid targets schema")
            release_recursion_guard()
            sys.exit(1)
    except Exception as e:
        logger.error("TARGETS_LOAD_FAILED", error=str(e))
        logger.error("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="failed", error_class=type(e).__name__, error_message=str(e))
        release_recursion_guard()
        sys.exit(1)
        
    total_targets_count = len(targets_list)
    if total_targets_count == 0:
        total_targets_count = 88  # 分母が0の場合のデフォルトフォールバック
        
    defects_file_path = validate_path(defects_path_str, allowed_scopes_global, read_only=True)
    
    logger.info("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="completed")
    
    # 2. MAPPING フェーズの開始
    active_phase = "mapping"
    logger.info("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="started")
    
    # 欠陥データのmtime取得（チェックポイント検証用）
    try:
        defects_mtime = os.path.getmtime(defects_file_path)
    except Exception as e:
        logger.error("DEFECTS_STAT_FAILED", error=str(e))
        logger.error("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="failed", error_class=type(e).__name__, error_message=str(e))
        release_recursion_guard()
        sys.exit(1)
        
    # 総行数プリスキャンと巨大サイズ行チェック (L9/L1 Dosガード)
    total_lines = 0
    try:
        with open(defects_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 10MB行制限
                if len(line.encode('utf-8')) > 10 * 1024 * 1024:
                    raise ValueError("Line size exceeds limit of 10MB (DoS Protection)")
                total_lines += 1
    except Exception as e:
        logger.error("DEFECTS_PRESCAN_FAILED", error=str(e))
        logger.error("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="failed", error_class=type(e).__name__, error_message=str(e))
        release_recursion_guard()
        sys.exit(1)
        
    # メトリクスの初期化
    metrics = {
        "dissipation_stop": {"count": 0, "severity_count": 0, "files": set(), "counterexamples": set()},
        "ambiguity_shrink": {"count": 0, "severity_count": 0, "files": set(), "counterexamples": set()},
        "min_action_workflow": {"count": 0, "severity_count": 0, "files": set(), "counterexamples": set()}
    }
    
    # チェックポイント読み込み
    chk = load_checkpoint(defects_mtime)
    start_offset = 0
    processed_rows = 0
    if chk:
        start_offset = chk["offset"]
        processed_rows = chk["processed_rows"]
        # セットから復元するために一時退避
        saved_metrics = chk["metrics"]
        for key in metrics:
            metrics[key]["count"] = saved_metrics[key]["count"]
            metrics[key]["severity_count"] = saved_metrics[key]["severity_count"]
            metrics[key]["files"] = set(saved_metrics[key]["files"])
            metrics[key]["counterexamples"] = set(saved_metrics[key]["counterexamples"])

    # 反例パスの一時バッファ用退避ファイル (L6/L9要件: メモリフットプリントコンパクション)
    tmp_buffer_path = pathlib.Path(app_data_dir) / "scratch" / "counterexamples.tmp"
    if tmp_buffer_path.exists() and not chk:
        tmp_buffer_path.unlink()
        
    buffer_counts = {
        "dissipation_stop": 0,
        "ambiguity_shrink": 0,
        "min_action_workflow": 0
    }
    
    invalid_data_count = 0
    parse_errors_details = []
    
    # 進行割合監視のしきい値
    progress_step = max(1, total_lines // 10)
    
    try:
        with open(defects_file_path, 'r', encoding='utf-8') as f:
            if start_offset > 0:
                f.seek(start_offset)
                
            for idx, line in enumerate(f, start=processed_rows + 1):
                # 進行ログ (10%ごと)
                if idx % progress_step == 0 or idx == total_lines:
                    progress_percentage = int((idx / total_lines) * 100) if total_lines > 0 else 100
                    logger.info("PROCESSING_PROGRESS", 
                                processed_count=idx, 
                                total_count=total_lines, 
                                progress_percentage=progress_percentage)
                                
                # パース
                try:
                    data = json.loads(line)
                except json.JSONDecodeError as jde:
                    invalid_data_count += 1
                    # 機密マスクを適用して生データを最大100文字抜粋 (L8要件)
                    excerpt = mask_secrets(line[:100].strip())
                    logger.warning("INVALID_DATA_RECORD", 
                                   file_path=defects_path_str, 
                                   line_number=idx, 
                                   raw_excerpt=excerpt, 
                                   error=str(jde))
                    parse_errors_details.append({"line": idx, "reason": f"JSONDecodeError: {str(jde)}"})
                    continue
                    
                # 必須キー検証
                required_keys = ["target", "pattern_class", "severity", "layer"]
                missing_keys = [k for k in required_keys if k not in data]
                if missing_keys:
                    invalid_data_count += 1
                    excerpt = mask_secrets(line[:100].strip())
                    logger.warning("INVALID_DATA_RECORD", 
                                   file_path=defects_path_str, 
                                   line_number=idx, 
                                   raw_excerpt=excerpt, 
                                   error=f"Missing keys: {missing_keys}")
                    parse_errors_details.append({"line": idx, "reason": f"Missing keys: {missing_keys}"})
                    continue
                    
                # データマッピングと集計
                target_file = data["target"]
                pattern = data["pattern_class"]
                severity = data["severity"]
                layer = data["layer"]
                
                is_severe = severity in ["高", "致命的", "high", "critical"]
                
                # パス正規化 (トラバーサル検証)
                try:
                    norm_target = validate_path(target_file, allowed_scopes_global)
                    norm_target_str = str(norm_target)
                except Exception:
                    # 監査対象ファイル自体がスコープ外の場合は警告してスキップ
                    continue
                
                # 散逸停止定理 (missing_stop_rule)
                if pattern == "missing_stop_rule":
                    metrics["dissipation_stop"]["count"] += 1
                    metrics["dissipation_stop"]["files"].add(norm_target_str)
                    if is_severe:
                        metrics["dissipation_stop"]["severity_count"] += 1
                        
                # 曖昧性収縮定理 (missing_golden_rule)
                elif pattern == "missing_golden_rule":
                    metrics["ambiguity_shrink"]["count"] += 1
                    metrics["ambiguity_shrink"]["files"].add(norm_target_str)
                    if is_severe:
                        metrics["ambiguity_shrink"]["severity_count"] += 1
                        
                # 最小作用ワークフロー定理 (missing_execution_workflow / missing_workflow)
                elif pattern in ["missing_execution_workflow", "missing_workflow"]:
                    metrics["min_action_workflow"]["count"] += 1
                    metrics["min_action_workflow"]["files"].add(norm_target_str)
                    if is_severe:
                        metrics["min_action_workflow"]["severity_count"] += 1

                # 反例候補の検出用（L2/L4かつ深刻な欠陥がこのファイルにあるかのマーキング）
                # 反例定義：対象定理の pattern_class が検出されているファイルのうち、L2 または L4 かつ深刻な欠陥が1件も存在しないファイル
                if layer in ["L2", "L4"] and is_severe:
                    # このファイルは反例ではないため、反例候補リストから除外するための追跡が必要
                    # 反例判定ロジックは統計フェーズにてマッピングされた全ファイルに対して最終評価します。
                    pass
                
                # 50,000行ごとのチェックポイント保存
                if idx % 50000 == 0:
                    current_offset = f.tell()
                    # セットはシリアライズできないためリストに変換
                    serializable_metrics = {}
                    for key, val in metrics.items():
                        serializable_metrics[key] = {
                            "count": val["count"],
                            "severity_count": val["severity_count"],
                            "files": list(val["files"]),
                            "counterexamples": list(val["counterexamples"])
                        }
                    save_checkpoint(current_offset, idx, serializable_metrics, defects_mtime)
                    
    except Exception as e:
        logger.error("DEFECTS_READ_FAILED", error=str(e))
        logger.error("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="failed", error_class=type(e).__name__, error_message=str(e))
        release_recursion_guard()
        sys.exit(1)
        
    logger.info("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="completed")
    
    # 3. STATISTICS フェーズの開始
    active_phase = "statistics"
    logger.info("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="started")
    
    # 縮退運転 (5%しきい値) の判定 (L9/L2/L5要件)
    invalid_ratio = (invalid_data_count / total_lines) if total_lines > 0 else 0
    if invalid_ratio > 0.05:
        # パースエラー多発による検証不可 (UNVERIFIABLE)
        logger.error("PARSE_ERRORS_SUMMARY", errors=parse_errors_details)
        logger.error("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="failed", error_class="ValueError", error_message="Parse errors exceeded 5% threshold")
        
        # すべての定理をUNVERIFIABLEとして強制終了
        # レポートおよびJSONの書き出し（hitl_required=True, result="UNVERIFIABLE"）
        unverifiable_results = {}
        for key in ["dissipation_stop", "ambiguity_shrink", "min_action_workflow"]:
            unverifiable_results[key] = {
                "result": "UNVERIFIABLE",
                "criticism": "データ破損、パースエラーの多発、または入力ファイルサイズが0であるため、当該定理の検証を実行できませんでした。",
                "improvement": "入力データである defects.jsonl の整合性を確認し、パースエラーの原因を修正した上で再実行してください。"
            }
        # エラーログにHITLメタデータを付与して終了
        logger.error("HITL_RECOVERY_REQUIRED",
                     hitl_recovery_context={
                         "recovery_action": "RESTORE_BACKUP",
                         "target_path": output_md_str
                     })
        
        # 簡易的にMarkdownとJSONを出力して終了コード2で終了
        # (出力処理はreportingフェーズの処理を流用)
        # 詳細は以下にアトミック出力
        write_unverifiable_reports(output_md_str, output_json_str, context_val, unverifiable_results)
        release_recursion_guard()
        sys.exit(2)

    # 4. 各定理の統計・合格判定の計算
    # 各ファイルの「L2/L4かつ深刻な欠陥」の存在有無を走査するための2パス目処理（メモリ節約のため、マッピングされたファイルリストに限定して再精査）
    # メモリ上の files セットから各ファイルを検査
    severe_l24_files = set()
    try:
        with open(defects_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    target = str(validate_path(data["target"], allowed_scopes_global))
                    layer = data["layer"]
                    severity = data["severity"]
                    is_severe = severity in ["高", "致命的", "high", "critical"]
                    if layer in ["L2", "L4"] and is_severe:
                        severe_l24_files.add(target)
                except Exception:
                    continue
    except Exception:
        pass

    results = {}
    counterexamples_truncated = False
    
    # 一時バッファファイルの追記ハンドラ
    tmp_buffer_write = None
    
    for key, pattern_name in [("dissipation_stop", "missing_stop_rule"), 
                              ("ambiguity_shrink", "missing_golden_rule"), 
                              ("min_action_workflow", "min_action")]:
        
        target_files = metrics[key]["files"]
        detected_count = len(target_files)
        
        # 1. 再現性の計算
        reproducibility_ratio = (detected_count / total_targets_count) if total_targets_count > 0 else 0
        repro_pass = reproducibility_ratio >= 0.30
        if detected_count == 0:
            repro_pass = True  # 分母0の例外合格ルート
            
        # 2. 影響度の計算
        total_defects = metrics[key]["count"]
        severe_defects = metrics[key]["severity_count"]
        impact_ratio = (severe_defects / total_defects) if total_defects > 0 else 0
        impact_pass = impact_ratio >= 0.50
        if total_defects == 0:
            impact_pass = True  # 分母0の例外合格ルート
            
        # 3. 反例比率の計算
        # 分母：当該 pattern_class が検出されているファイル数 (detected_count)
        # 分子：そのうち、L2/L4かつ深刻な欠陥が1件も存在しないファイル（＝反例）数
        counterexamples = []
        for f in target_files:
            if f not in severe_l24_files:
                counterexamples.append(f)
                
        counterexample_count = len(counterexamples)
        counterexample_ratio = (counterexample_count / detected_count) if detected_count > 0 else 0
        counter_pass = counterexample_ratio <= 0.10
        if detected_count == 0:
            counter_pass = True  # 分母0の例外合格ルート
            
        # 反例リストのメモリ上限(1000件)＆コンパクション (L6/L9要件)
        stored_counterexamples = []
        for c_path in counterexamples:
            if len(stored_counterexamples) < 1000:
                stored_counterexamples.append(c_path)
            else:
                counterexamples_truncated = True
                # 一時ファイルにストリーム退避 (0600)
                if not tmp_buffer_write:
                    # アペンドモード、0600で開く
                    fd = os.open(tmp_buffer_path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
                    tmp_buffer_write = os.fdopen(fd, 'a')
                tmp_buffer_write.write(f"{key}:{c_path}\n")
                buffer_counts[key] += 1
                
        metrics[key]["counterexamples"] = set(stored_counterexamples)
        
        # 総合判定
        passed = repro_pass and impact_pass and counter_pass
        results[key] = {
            "result": "PASS" if passed else "FAIL",
            "reproducibility": reproducibility_ratio,
            "repro_pass": repro_pass,
            "impact": impact_ratio,
            "impact_pass": impact_pass,
            "counterexample_ratio": counterexample_ratio,
            "counter_pass": counter_pass,
            "counterexamples_count": counterexample_count,
            "detected_count": detected_count,
            "total_defects": total_defects,
            "severe_defects": severe_defects
        }

    if tmp_buffer_write:
        tmp_buffer_write.flush()
        tmp_buffer_write.close()

    # criticism & improvement の動的テキストルールエンジン適用
    # 複数未達時は改行結合 (L2要件)
    for key in results:
        res = results[key]
        if res["result"] == "PASS":
            res["criticism"] = 'すべての検証基準を満たしていますが、将来的な仕様変更時の回帰を防止するため、継続的な監視を推奨します。'
            res["improvement"] = '現在の行動仕様および設計ルールを維持し、定期的な監査を実行してください。'
        else:
            criticisms = []
            improvements = []
            if not res["repro_pass"]:
                criticisms.append('定理の再現性基準（30%以上）に達していません。')
                improvements.append('対象のルール（例: stop_rule, golden_rule）が定義されていないファイルの割合を減らすため、エージェントの基本指示に該当ルールを明記してください。')
            if not res["impact_pass"]:
                criticisms.append('検出された欠陥における深刻度（高・致命的）の割合が50%未満です。')
                improvements.append('深刻な欠陥の発生を抑えるため、該当する設計レイヤーのバリデーションを強化してください。')
            if not res["counter_pass"]:
                criticisms.append('深刻な欠陥が検出されなかったファイル（反例）の割合が10%を超えています。')
                improvements.append('例外ケースのハンドリングルールを見直し、反例となる健全なファイルでもルール遵守が徹底されるよう設計を修正してください。')
                
            res["criticism"] = "\n".join(criticisms)
            res["improvement"] = "\n".join(improvements)

    logger.info("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="completed")
    
    # 4. REPORTING フェーズの開始
    active_phase = "reporting"
    logger.info("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="started")
    
    # 一時退避ファイルからの反例リスト読み出しとマージ (L6要件)
    extended_counterexamples = {
        "dissipation_stop": list(metrics["dissipation_stop"]["counterexamples"]),
        "ambiguity_shrink": list(metrics["ambiguity_shrink"]["counterexamples"]),
        "min_action_workflow": list(metrics["min_action_workflow"]["counterexamples"])
    }
    
    if counterexamples_truncated and tmp_buffer_path.exists():
        try:
            with open(tmp_buffer_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if ":" in line:
                        k, p_path = line.split(":", 1)
                        if k in extended_counterexamples:
                            extended_counterexamples[k].append(p_path)
            # 一時ファイルの確実なクリーンアップ
            tmp_buffer_path.unlink()
        except Exception as e:
            logger.warning("BUFFER_MERGE_FAILED", error=str(e))

    # hitl_required 判定
    # 1. いずれかの定理が不合格
    # 2. counterexamples_truncated が true (L9/L6要件)
    # 3. 入力データ破損による分母0の警告
    any_fail = any(res["result"] == "FAIL" for res in results.values())
    hitl_required = any_fail or counterexamples_truncated
    
    # すべての分母が0かどうかのチェック
    all_zero_denominator = all(res["detected_count"] == 0 for res in results.values())
    if all_zero_denominator:
        hitl_required = True
        logger.warning("DATA_CORRUPTION_DETECTED", reason="All theorems have zero denominators")
        
    # JSONメタデータの動的テキストXMLカプセル化 (L9/L4/L3セキュリティ要件)
    # XMLデリミタで囲み、エスケープ・サニタイズを適用
    for key in results:
        c_raw = results[key]["criticism"]
        i_raw = results[key]["improvement"]
        # サニタイズ（制御文字除去、HTMLエスケープ）
        c_sanitized = html_escape(c_raw)
        i_sanitized = html_escape(i_raw)
        
        # カプセル化されたプロンプトインジェクションガード
        results[key]["criticism"] = f"<untrusted_metadata>\n{c_sanitized}\n</untrusted_metadata>"
        results[key]["improvement"] = f"<untrusted_metadata>\n{i_sanitized}\n</untrusted_metadata>"

    # 1. JSON レポートの生成
    json_output_data = {
        "workflow_context": context_val,
        "hitl_required": hitl_required,
        "counterexamples_truncated": counterexamples_truncated,
        "results": {}
    }
    for key in results:
        json_output_data["results"][key] = {
            "result": results[key]["result"],
            "reproducibility": results[key]["reproducibility"],
            "impact": results[key]["impact"],
            "counterexample_ratio": results[key]["counterexample_ratio"],
            "counterexamples": extended_counterexamples[key],
            "criticism": results[key]["criticism"],
            "improvement": results[key]["improvement"]
        }
    
    json_str = json.dumps(json_output_data, indent=2, ensure_ascii=False)
    execute_atomic_write(output_json_str, json_str, is_json=True)
    
    # 2. Markdown レポートの生成
    md_content = generate_markdown_report(results, extended_counterexamples, total_targets_count, all_zero_denominator, counterexamples_truncated)
    execute_atomic_write(output_md_str, md_content)
    
    # 警告シグナルログの出力
    if hitl_required:
        logger.warning("HITL_PENDING_APPROVAL", workflow_context=context_val)
        
    # 正常終了時のクリーンアップ (チェックポイント削除)
    if checkpoint_path and checkpoint_path.exists():
        try:
            checkpoint_path.unlink()
        except Exception:
            pass
            
    # 再帰カウンタのデクリメントおよびロック解放
    release_recursion_guard()
    
    logger.info("WORKFLOW_PHASE_CHANGED", phase=active_phase, status="completed")
    sys.exit(0)

def html_escape(text: str) -> str:
    """特殊文字を安全にエスケープする"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

def generate_markdown_report(results: dict, counterexamples: dict, total_targets: int, all_zero: bool, truncated: bool) -> str:
    """仕様に従ってマークダウンレポートの文章を組み立てる（インジェクション対策付き）"""
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    
    md = []
    md.append(f"# 定理検証結果レポート")
    md.append(f"- **生成日時**: {t}")
    md.append(f"- **検証対象総数**: {total_targets} 件")
    md.append("")
    
    if all_zero:
        md.append("> [!WARNING]")
        md.append("> **HITL確認要求**: 入力欠陥データから有効なレコードが1件も取得されず、すべての定理の分母が0となりました。データ破損の疑いがあるため、オペレータによる確認が必要です。")
        md.append("")
        
    if truncated:
        md.append("> [!NOTE]")
        md.append("> **反例切り捨て発生**: 反例リストのバッファ上限（1,000件）を超えたため、メモリ保護の観点から一部の反例パスがストリーム退避されました。")
        md.append("")

    for key, name in [("dissipation_stop", "散逸停止定理"), 
                      ("ambiguity_shrink", "曖昧性収縮定理"), 
                      ("min_action_workflow", "最小作用ワークフロー定理")]:
        
        res = results[key]
        status = "合格" if res["result"] == "PASS" else "不合格"
        
        md.append(f"## {name} (判定: {status})")
        md.append(f"- **再現性 (分母: {total_targets})**: {res['reproducibility'] * 100:.1f}% ({res['detected_count']} 件)")
        md.append(f"- **影響度 (分母: {res['total_defects']})**: {res['impact'] * 100:.1f}% ({res['severe_defects']} 件)")
        md.append(f"- **反例比率 (分母: {res['detected_count']})**: {res['counterexample_ratio'] * 100:.1f}% ({res['counterexamples_count']} 件)")
        md.append("")
        
        # エスケープを施してマークダウンに埋め込む (プロンプトインジェクションガード)
        criticism_esc = html_escape(res["criticism"])
        improvement_esc = html_escape(res["improvement"])
        
        md.append("### ダメだし (Criticism)")
        md.append(criticism_esc)
        md.append("")
        md.append("### 改善点 (Improvement)")
        md.append(improvement_esc)
        md.append("")
        
        md.append("### 反例ファイルリスト")
        c_list = counterexamples[key]
        if c_list:
            for c in c_list[:10]:  # レポートには最初の10件のみ表示
                md.append(f"- `{html_escape(c)}`")
            if len(c_list) > 10:
                md.append(f"- ... (他 {len(c_list) - 10} 件)")
        else:
            md.append("反例なし")
        md.append("")
        md.append("---")
        
    return "\n".join(md)

def write_unverifiable_reports(output_md: str, output_json: str, context: str, unverifiable_results: dict):
    """5%以上の重大パースエラーによる検証不可時の空レポート作成処理"""
    json_data = {
        "workflow_context": context,
        "hitl_required": True,
        "counterexamples_truncated": False,
        "results": unverifiable_results
    }
    # JSON出力
    try:
        execute_atomic_write(output_json, json.dumps(json_data, indent=2, ensure_ascii=False), is_json=True)
    except Exception:
        pass
        
    # MD出力
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    md = [
        f"# 定理検証結果レポート",
        f"- **生成日時**: {t}",
        f"- **検証不可 (UNVERIFIABLE)**",
        "",
        "> [!CAUTION]",
        "> **データパースしきい値(5%)超過による異常停止**: 入力欠陥データの破損率が5%を超えたため、統計処理を中断しました。仕様に基づき、すべての定理は検証不可とみなされます。",
        ""
    ]
    for key, name in [("dissipation_stop", "散逸停止定理"), 
                      ("ambiguity_shrink", "曖昧性収縮定理"), 
                      ("min_action_workflow", "最小作用ワークフロー定理")]:
        md.append(f"## {name} (判定: 検証不可)")
        md.append("### ダメだし (Criticism)")
        md.append(unverifiable_results[key]["criticism"])
        md.append("")
        md.append("### 改善点 (Improvement)")
        md.append(unverifiable_results[key]["improvement"])
        md.append("")
        md.append("---")
        
    try:
        execute_atomic_write(output_md, "\n".join(md))
    except Exception:
        pass

if __name__ == "__main__":
    main()
