# Sora 2 ビデオ生成 Web サービス

OpenAI の Sora 2 API を使った簡単なビデオ生成アプリ（サーバ + ブラウザUI）。

## セットアップ

### 1. 仮想環境の作成

```bash
cd /Users/keiichi/Desktop/Work/python/vgen-sora2
conda create -n vgen-sora2 python=3.9 -y
conda activate vgen-sora2
```

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 3. APIキーの設定

`.env`ファイルを編集し、OpenAI APIキーを設定：

```env
OPENAI_API_KEY=your-actual-api-key-here
```

## 起動方法

```bash
conda activate vgen-sora2
python app.py
```

ブラウザで `http://localhost:5001` にアクセス

## 使い方（概要）

1. プロンプト欄に生成したいビデオの内容を入力
2. モデル（Sora 2 または Sora 2 Pro）を選択
3. 「ビデオを生成」ボタンをクリック
4. 生成完了まで待機（ステータスが自動更新されます）
5. 完成したビデオがページ上で再生されます（最終フレームPNGが一覧に追加）

### Image to Video
- 画像をアップロード、または「最近抽出された最終フレーム」から選択して実行

### 保存先
- 右上の「保存先」ボタンで `static/` フォルダを開けます

## 機能

- シンプルで使いやすいUI
- リアルタイムの生成ステータス表示
- 自動ポーリングによる進捗確認
- 生成されたビデオの即時プレビュー
- 画像の自動リサイズ＆クロップ
- 最終フレームPNGの自動抽出（失敗時は `/reextract/<video_id>` で再抽出）
- レスポンシブデザイン

## 注意事項

- APIキーが必要です
- ビデオ生成には時間がかかります（数分程度）
- 生成されたビデオは`static/`フォルダに保存されます（起動時に7日より古いmp4は自動削除）
- API使用料金が発生します

## 補足
- このアプリは **Sora 2 API** を使用しています（参考: [Video Generation Guide](https://platform.openai.com/docs/guides/video-generation?lang=python)）。
- 利用には **組織の本人確認（Organization Verification）** が必要な場合があります（参考: [OpenAI 組織設定](https://platform.openai.com/settings/organization)）。
- **テキスト to ビデオ**／**イメージ to ビデオ** の両方に対応しています。
- 生成秒数は **4秒／8秒／12秒** から選べます。
- サイズは **縦長（720x1280）**／**横長（1280x720）** のいずれかを選べます。
- API経由のため **Soraの「すかし」は入りません**。
- **商用利用は可能** ですが、OpenAIの規約・ポリシー等に従ってください。
- 動画生成時に **最終フレームをPNGで保存** し、サムネ一覧から選択して続編（延長）を簡単に生成できます。

