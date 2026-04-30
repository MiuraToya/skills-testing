# 実行環境プロファイル: Python + pytest

このファイルは Python + pytest 向けの具体パターンをまとめる。

## 目次

1. [一次情報](#runtime-python-pytest-source)
2. [レイアウトとimport mode](#runtime-python-pytest-layout)
3. [Fixture](#runtime-python-pytest-fixture)
4. [Parametrize](#runtime-python-pytest-parametrize)
5. [Assertion / raises](#runtime-python-pytest-assertion)
6. [tmp_path](#runtime-python-pytest-tmp-path)
7. [monkeypatch](#runtime-python-pytest-monkeypatch)
8. [Integrationでの実依存/フェイク運用](#runtime-python-pytest-integration)
9. [skip / xfail](#runtime-python-pytest-skip-xfail)
10. [決定論チェック](#runtime-python-pytest-determinism)

<a id="runtime-python-pytest-source"></a>
## 一次情報

- Good Integration Practices: https://docs.pytest.org/en/stable/explanation/goodpractices.html
- Parametrize: https://docs.pytest.org/en/stable/how-to/parametrize.html
- Assertions / raises: https://docs.pytest.org/en/stable/how-to/assert.html
- monkeypatch: https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- tmp_path: https://docs.pytest.org/en/stable/how-to/tmp_path.html

<a id="runtime-python-pytest-layout"></a>
## 1. レイアウトとimport mode

- 多くのプロジェクトでは `src/` + `tests/` 構成を優先する。
- 新規プロジェクトでは `--import-mode=importlib` を推奨する。

```toml
[pytest]
addopts = ["--import-mode=importlib"]
```

<a id="runtime-python-pytest-fixture"></a>
## 2. Fixture

- setup共有は fixture で明示的に行う。
- scope（function/module/session）は意図を持って選ぶ。
- fixture間の依存は最小限に保つ。

```python
import pytest


@pytest.fixture
def user_repo(tmp_path):
    return SqliteRepo(tmp_path / "test.db")
```

<a id="runtime-python-pytest-parametrize"></a>
## 3. Parametrize

- 条件行列には `@pytest.mark.parametrize` を使う。
- ケース別の期待失敗には `pytest.param(..., marks=...)` を使う。
- mutableな引数は「そのまま渡される」ため、テスト内変更で汚染しない。

```python
import pytest


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("A", "a"),
        (" B ", "b"),
        pytest.param("", "", marks=pytest.mark.xfail(reason="仕様検討中")),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected
```

<a id="runtime-python-pytest-assertion"></a>
## 4. Assertion / raises

- `assert` をそのまま使い、pytestの失敗表示を活用する。
- 例外検証は `pytest.raises` のコンテキストマネージャ形式を優先する。
- 例外メッセージは `match=` で正規表現検証する。

```python
import pytest


def test_divide_by_zero_raises():
    with pytest.raises(ZeroDivisionError, match="division"):
        divide(1, 0)
```

<a id="runtime-python-pytest-tmp-path"></a>
## 5. tmp_path

- ファイルI/Oテストは `tmp_path`（`pathlib.Path`）を使う。
- 新規コードで `tmpdir` は使わない。

```python
def test_write_report(tmp_path):
    p = tmp_path / "report.txt"
    p.write_text("ok", encoding="utf-8")
    assert p.read_text(encoding="utf-8") == "ok"
```

<a id="runtime-python-pytest-monkeypatch"></a>
## 6. monkeypatch（限定利用）

- 原則として、外部依存の置き換えは `autospec/spec_set` 付きのMockを優先する。
- `monkeypatch` は環境変数、モジュール定数、時刻/乱数などのプロセス依存値の制御に限定する。
- `monkeypatch.setattr(..., raising=True)` を使い、対象属性が存在しない変更を検知する。

```python
from unittest.mock import patch


def test_service_calls_client_with_expected_signature():
    with patch("app.service.ExternalClient", autospec=True) as ClientMock:
        client = ClientMock.return_value
        client.fetch_user.return_value = {"id": "u1"}

        result = run_service("u1")

        client.fetch_user.assert_called_once_with("u1")
        assert result["id"] == "u1"
```

```python
from unittest.mock import create_autospec


class Gateway:
    def send(self, user_id: str, amount: int) -> bool:
        ...


def test_gateway_contract_with_spec_set():
    gateway = create_autospec(Gateway, instance=True, spec_set=True)
    gateway.send.return_value = True

    assert pay(gateway, "u1", 100) is True
    gateway.send.assert_called_once_with("u1", 100)
```

```python
def test_uses_env_token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-token")
    assert load_token() == "test-token"
```

<a id="runtime-python-pytest-integration"></a>
## 7. Integrationでの実依存/フェイク運用

- DB境界の検証では、実DBを使うテストを最低1系統は持つ（例: MySQLコンテナ）。
- 外部クラウドサービスは、速度と再現性のためにエミュレータ/フェイク（例: moto）を優先する。
- 使い分けの基本方針:
- SQL/トランザクション/インデックス/制約を確認したい: 実DBコンテナ
- SDK呼び出し、バケット操作、キー設計などを確認したい: moto
- 本番クラウド実環境は、CIの常時実行ではなく限定的な検証ジョブへ分離する。

```python
import os
import pytest
from sqlalchemy import create_engine, text


@pytest.fixture(scope="session")
def mysql_dsn():
    # 例: docker compose up -d mysql 済みを前提にDSNを受け取る
    return os.environ["TEST_MYSQL_DSN"]


def test_user_repository_with_real_mysql(mysql_dsn):
    engine = create_engine(mysql_dsn)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users(id, name) VALUES (1, 'alice')"))
        row = conn.execute(text("SELECT name FROM users WHERE id = 1")).first()
    assert row[0] == "alice"
```

```python
import boto3
from moto import mock_aws


@mock_aws
def test_s3_upload_with_moto():
    s3 = boto3.client("s3", region_name="ap-northeast-1")
    s3.create_bucket(
        Bucket="test-bucket",
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3.put_object(Bucket="test-bucket", Key="a.txt", Body=b"hello")
    obj = s3.get_object(Bucket="test-bucket", Key="a.txt")
    assert obj["Body"].read() == b"hello"
```

<a id="runtime-python-pytest-skip-xfail"></a>
## 8. skip / xfail

- 実行前提を満たせないときは `skip`。
- 既知不具合や未実装仕様は `xfail`。
- `XPASS` をCI失敗扱いにしたい場合は strict運用を採用する。

<a id="runtime-python-pytest-determinism"></a>
## 9. 決定論チェック

- 乱数を固定する（seedまたは固定データ）。
- 時刻依存を固定する（時計抽象化やfreeze）。
- 実ネットワークを原則使わない。
- テスト間共有状態を排除する。
- 任意順実行でも同結果になることを確認する。
