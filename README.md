# Reservation API（実験用コードベース）

Agent Skill の効果測定（UT/IT戦略比較）向けのサンプルです。  
アーキテクチャは DDD 寄りのレイヤード構成です。

- `domain`: エンティティと不変条件のみ
- `application`: ユースケースと処理のオーケストレーション
- `infrastructure`: SQLAlchemy リポジトリと Unit of Work
- `presentation`: FastAPI のルーティングとレスポンス変換

実行環境:
- Python 3.14
- 依存管理/実行: uv

## Docker Compose で起動

```bash
docker compose up --build
```

起動後のアクセス先:

- `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`

## uv でローカル実行

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## 主なエンドポイント

### 会議室作成

`POST /api/v1/rooms`

```json
{
  "name": "Room A",
  "capacity": 8
}
```

### 会議室一覧取得

`GET /api/v1/rooms`

### 予約作成

`POST /api/v1/reservations`

```json
{
  "room_id": 1,
  "guest_name": "Taro",
  "attendee_count": 4,
  "start_at": "2026-05-01T10:00:00+09:00",
  "end_at": "2026-05-01T11:00:00+09:00"
}
```

### 予約キャンセル

`POST /api/v1/reservations/{reservation_id}/cancel`

```json
{
  "canceled_at": "2026-05-01T08:30:00+09:00"
}
```

## ドメイン不変条件

- 予約時刻はタイムゾーン付き日時であること
- 開始/終了時刻は30分単位であること
- 予約は営業時間内（09:00-18:00）であること
- 予約は同日内で開始・終了すること
- 参加人数が会議室定員を超えないこと
- 有効な予約同士の時間重複を禁止すること
- キャンセルは開始60分前までに行うこと
