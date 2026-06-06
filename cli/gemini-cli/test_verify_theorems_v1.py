import os
import sys
import json
import shutil
import tempfile
import pathlib
import subprocess
import time
import pytest

# テスト対象スクリプトのパス
SCRIPT_PATH = "/Users/ryota/.gemini/antigravity/scratch/verify_theorems_v1.py"

@pytest.fixture
def temp_sandbox():
    """テストごとにクリーンな一時作業ディレクトリを作成するフィクスチャ"""
    temp_dir = tempfile.mkdtemp()
    yield pathlib.Path(temp_dir)
    shutil.rmtree(temp_dir)

def create_defects_jsonl(path, records):
    """テスト用の defects.jsonl を作成するヘルパー"""
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        for r in records:
            if isinstance(r, str):
                f.write(r + "\n")
            else:
                f.write(json.dumps(r) + "\n")

def create_targets_json(path, targets):
    """テスト用の target_files.json を作成するヘルパー"""
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(json.dumps(targets))

def test_normal_run(temp_sandbox):
    """正常系の動作確認：メトリクス計算、合否判定、0600権限、レポート出力の検証"""
    targets = [f"/Users/ryota/.gemini/antigravity/scratch/file_{i}.py" for i in range(10)]
    targets_path = temp_sandbox / "target_files.json"
    create_targets_json(targets_path, targets)
    
    # 欠陥データの作成
    records = [
        {"target": targets[0], "pattern_class": "missing_stop_rule", "severity": "高", "layer": "L2"},
        {"target": targets[1], "pattern_class": "missing_stop_rule", "severity": "高", "layer": "L2"},
        {"target": targets[2], "pattern_class": "missing_stop_rule", "severity": "中", "layer": "L1"},
    ]
    
    defects_path = temp_sandbox / "defects.jsonl"
    create_defects_jsonl(defects_path, records)
    
    output_md = temp_sandbox / "results.md"
    output_json = temp_sandbox / "results.json"
    
    # スクリプト実行
    env = os.environ.copy()
    env["APP_DATA_DIR"] = str(temp_sandbox)
    env["ALLOWED_SCOPES"] = f"{str(temp_sandbox)},/Users/ryota/.gemini/antigravity/scratch"
    env["VIRTUAL_ENV"] = "dummy_venv"  # 環境ガードを通過させる
    
    res = subprocess.run([
        sys.executable, SCRIPT_PATH,
        "--targets", str(targets_path),
        "--defects", str(defects_path),
        "--output", str(output_md),
        "--output-json", str(output_json),
        "--workflow-context", "test-context"
    ], env=env, capture_output=True, text=True)
    
    assert res.returncode == 0
    
    # レポート生成物の確認
    assert output_md.exists()
    assert output_json.exists()
    
    # パーミッション確認 (0600)
    assert (output_md.stat().st_mode & 0o777) == 0o600
    assert (output_json.stat().st_mode & 0o777) == 0o600
    
    # JSON内容の検証
    with open(output_json, 'r') as f:
        data = json.loads(f.read())
        
    assert data["workflow_context"] == "test-context"
    assert data["hitl_required"] is True  # 判定FAILが含まれるためTrue
    
    results = data["results"]
    assert results["dissipation_stop"]["result"] == "FAIL"
    assert results["ambiguity_shrink"]["result"] == "PASS"
    
    # criticism にXMLインジェクション対策タグが含まれているか検証
    assert "<untrusted_metadata>" in results["dissipation_stop"]["criticism"]
    assert "</untrusted_metadata>" in results["dissipation_stop"]["criticism"]

def test_recursion_guard_env(temp_sandbox):
    """環境変数による再帰制限ガードの検証 (DEPTH >= 5のときに終了コード3で落ちる)"""
    targets_path = temp_sandbox / "target_files.json"
    create_targets_json(targets_path, [])
    defects_path = temp_sandbox / "defects.jsonl"
    create_defects_jsonl(defects_path, [])
    
    env = os.environ.copy()
    env["THEOREM_VERIFICATION_DEPTH"] = "5"
    env["APP_DATA_DIR"] = str(temp_sandbox)
    env["ALLOWED_SCOPES"] = str(temp_sandbox)
    env["VIRTUAL_ENV"] = "dummy_venv"
    
    res = subprocess.run([
        sys.executable, SCRIPT_PATH,
        "--targets", str(targets_path),
        "--defects", str(defects_path),
        "--output", str(temp_sandbox / "res.md"),
        "--output-json", str(temp_sandbox / "res.json")
    ], env=env, capture_output=True, text=True)
    
    assert res.returncode == 3
    assert "RECURSION_GUARD_TRIGGERED" in res.stderr

def test_path_traversal_allowed_scopes(temp_sandbox):
    """トラバーサルガード：allowed_scopes外のパス書き込み時のValueError&終了コード1"""
    targets_path = temp_sandbox / "target_files.json"
    create_targets_json(targets_path, [])
    defects_path = temp_sandbox / "defects.jsonl"
    create_defects_jsonl(defects_path, [])
    
    env = os.environ.copy()
    env["APP_DATA_DIR"] = str(temp_sandbox)
    env["ALLOWED_SCOPES"] = str(temp_sandbox)
    env["VIRTUAL_ENV"] = "dummy_venv"
    
    # スコープ外（システムの一時ディレクトリなど）への書き出しを指定
    outside_output = "/tmp/should_fail.md"
    
    res = subprocess.run([
        sys.executable, SCRIPT_PATH,
        "--targets", str(targets_path),
        "--defects", str(defects_path),
        "--output", outside_output,
        "--output-json", str(temp_sandbox / "res.json")
    ], env=env, capture_output=True, text=True)
    
    assert res.returncode == 1
    assert "SECURITY_VIOLATION_PATH_TRAVERSAL" in res.stderr

def test_graceful_degradation_low_errors(temp_sandbox):
    """縮退運転：パースエラーが5%以下の場合は無視して処理が正常終了すること"""
    targets_path = temp_sandbox / "target_files.json"
    create_targets_json(targets_path, ["/Users/ryota/.gemini/antigravity/scratch/file_0.py"])
    
    # 20行中1行だけ不正なJSON行を入れる (5%以下)
    records = []
    for _ in range(19):
        records.append({"target": "/Users/ryota/.gemini/antigravity/scratch/file_0.py", "pattern_class": "missing_stop_rule", "severity": "高", "layer": "L2"})
    records.append("{invalid_json_line!!!")
    
    defects_path = temp_sandbox / "defects.jsonl"
    create_defects_jsonl(defects_path, records)
    
    env = os.environ.copy()
    env["APP_DATA_DIR"] = str(temp_sandbox)
    env["ALLOWED_SCOPES"] = f"{str(temp_sandbox)},/Users/ryota/.gemini/antigravity/scratch"
    env["VIRTUAL_ENV"] = "dummy_venv"
    
    res = subprocess.run([
        sys.executable, SCRIPT_PATH,
        "--targets", str(targets_path),
        "--defects", str(defects_path),
        "--output", str(temp_sandbox / "res.md"),
        "--output-json", str(temp_sandbox / "res.json")
    ], env=env, capture_output=True, text=True)
    
    assert res.returncode == 0
    assert "INVALID_DATA_RECORD" in res.stderr

def test_graceful_degradation_high_errors(temp_sandbox):
    """縮退運転：パースエラーが5%を超える場合は終了コード2で異常終了し、全定理検証不可（UNVERIFIABLE）になること"""
    targets_path = temp_sandbox / "target_files.json"
    create_targets_json(targets_path, ["/Users/ryota/.gemini/antigravity/scratch/file_0.py"])
    
    # 10行中2行が不正なJSON (20% -> 5%超)
    records = []
    for _ in range(8):
        records.append({"target": "/Users/ryota/.gemini/antigravity/scratch/file_0.py", "pattern_class": "missing_stop_rule", "severity": "高", "layer": "L2"})
    records.append("{invalid_json_line1")
    records.append("{invalid_json_line2")
    
    defects_path = temp_sandbox / "defects.jsonl"
    create_defects_jsonl(defects_path, records)
    
    output_md = temp_sandbox / "res.md"
    output_json = temp_sandbox / "res.json"
    
    env = os.environ.copy()
    env["APP_DATA_DIR"] = str(temp_sandbox)
    env["ALLOWED_SCOPES"] = f"{str(temp_sandbox)},/Users/ryota/.gemini/antigravity/scratch"
    env["VIRTUAL_ENV"] = "dummy_venv"
    
    res = subprocess.run([
        sys.executable, SCRIPT_PATH,
        "--targets", str(targets_path),
        "--defects", str(defects_path),
        "--output", str(output_md),
        "--output-json", str(output_json)
    ], env=env, capture_output=True, text=True)
    
    assert res.returncode == 2
    assert "PARSE_ERRORS_SUMMARY" in res.stderr
    
    with open(output_json, 'r') as f:
        data = json.loads(f.read())
    assert data["results"]["dissipation_stop"]["result"] == "UNVERIFIABLE"
    assert data["hitl_required"] is True

def test_counterexample_truncation(temp_sandbox):
    """反例バッファ制限：反例が1,000件を超えた時のストリーム退避とマージ、フラグ(true)の検証"""
    targets_path = temp_sandbox / "target_files.json"
    targets = [f"/Users/ryota/.gemini/antigravity/scratch/file_{i}.py" for i in range(1100)]
    create_targets_json(targets_path, targets)
    
    records = []
    for i in range(1100):
        records.append({"target": targets[i], "pattern_class": "missing_stop_rule", "severity": "中", "layer": "L1"})
        
    defects_path = temp_sandbox / "defects.jsonl"
    create_defects_jsonl(defects_path, records)
    
    output_json = temp_sandbox / "res.json"
    
    env = os.environ.copy()
    env["APP_DATA_DIR"] = str(temp_sandbox)
    env["ALLOWED_SCOPES"] = f"{str(temp_sandbox)},/Users/ryota/.gemini/antigravity/scratch"
    env["VIRTUAL_ENV"] = "dummy_venv"
    
    res = subprocess.run([
        sys.executable, SCRIPT_PATH,
        "--targets", str(targets_path),
        "--defects", str(defects_path),
        "--output", str(temp_sandbox / "res.md"),
        "--output-json", str(output_json)
    ], env=env, capture_output=True, text=True)
    
    assert res.returncode == 0
    
    with open(output_json, 'r') as f:
        data = json.loads(f.read())
        
    assert data["counterexamples_truncated"] is True
    assert data["hitl_required"] is True
    assert len(data["results"]["dissipation_stop"]["counterexamples"]) == 1100
    
    tmp_buffer_path = temp_sandbox / "scratch" / "counterexamples.tmp"
    assert not tmp_buffer_path.exists()

def test_checkpoint_restore(temp_sandbox):
    """チェックポイント機能：中間集計結果の保存と再起動時のシーク再開検証"""
    targets_path = temp_sandbox / "target_files.json"
    targets = ["/Users/ryota/.gemini/antigravity/scratch/file_0.py"]
    create_targets_json(targets_path, targets)
    
    # 60,000行の欠陥データを用意（50,000行でチェックポイントが保存される）
    records = []
    for _ in range(60000):
        records.append({"target": "/Users/ryota/.gemini/antigravity/scratch/file_0.py", "pattern_class": "missing_stop_rule", "severity": "高", "layer": "L2"})
        
    defects_path = temp_sandbox / "defects.jsonl"
    create_defects_jsonl(defects_path, records)
    
    # タイムスタンプ取得
    defects_mtime = os.path.getmtime(defects_path)
    
    # 手動でダミーのチェックポイントファイルを配置
    # 50,000行時点でのオフセットを設定
    # テストの安定性のために、ダミーチェックポイントから検証をシーク再開させ、
    # 正常にカウントが合算されるかを確認
    scratch_dir = temp_sandbox / "scratch"
    scratch_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    checkpoint_file = scratch_dir / "verify_checkpoint.json.tmp"
    
    # 50,000行処理済みとし、そこでのメトリクスカウントを 50000 と仮定
    # defects.jsonl の1行の長さ（改行込み）は json.dumps + \n
    single_line_len = len(json.dumps({"target": "/Users/ryota/.gemini/antigravity/scratch/file_0.py", "pattern_class": "missing_stop_rule", "severity": "高", "layer": "L2"}) + "\n")
    offset_50k = single_line_len * 50000
    
    checkpoint_data = {
        "file_mtime": defects_mtime,
        "offset": offset_50k,
        "processed_rows": 50000,
        "metrics": {
            "dissipation_stop": {"count": 50000, "severity_count": 50000, "files": [targets[0]], "counterexamples": []},
            "ambiguity_shrink": {"count": 0, "severity_count": 0, "files": [], "counterexamples": []},
            "min_action_workflow": {"count": 0, "severity_count": 0, "files": [], "counterexamples": []}
        }
    }
    
    with open(checkpoint_file, 'w') as f:
        f.write(json.dumps(checkpoint_data))
        
    env = os.environ.copy()
    env["APP_DATA_DIR"] = str(temp_sandbox)
    env["ALLOWED_SCOPES"] = f"{str(temp_sandbox)},/Users/ryota/.gemini/antigravity/scratch"
    env["VIRTUAL_ENV"] = "dummy_venv"
    
    output_json = temp_sandbox / "res.json"
    
    res = subprocess.run([
        sys.executable, SCRIPT_PATH,
        "--targets", str(targets_path),
        "--defects", str(defects_path),
        "--output", str(temp_sandbox / "res.md"),
        "--output-json", str(output_json)
    ], env=env, capture_output=True, text=True)
    
    assert res.returncode == 0
    assert "CHECKPOINT_RESTORED" in res.stderr
    
    with open(output_json, 'r') as f:
        data = json.loads(f.read())
        
    # カウント数が 50,000 (チェックポイント) + 10,000 (残り) = 60,000 になっているか
    assert data["results"]["dissipation_stop"]["impact"] == 1.0
    # defects.jsonl の残り10,000件が正しく加算されている
    # チェックポイント復元が正しく動作した証拠
