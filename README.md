# Sora 2 ビデオ生成Webサービス

OpenAIのSora 2 APIを使用したビデオ生成Webアプリケーション

## セットアップ

### 1. 仮想環境の作成

```bash
cd /Users/keiichi/Desktop/Work/python/vgen-sora2
conda create -n vgen-sora2 python=3.9
conda activate vgen-sora2
```

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 3. APIキーの設定

`.env`ファイルを編集し、OpenAI APIキーを設定：

```
OPENAI_API_KEY=your-actual-api-key-here
```

## 起動方法

```bash
conda activate vgen-sora2
python app.py
```

ブラウザで http://localhost:5000 にアクセス

## 使い方

1. プロンプト欄に生成したいビデオの内容を入力
2. モデル（Sora 2 または Sora 2 Pro）を選択
3. 「ビデオを生成」ボタンをクリック
4. 生成完了まで待機（ステータスが自動更新されます）
5. 完成したビデオがページ上で再生されます

## 機能

- シンプルで使いやすいUI
- リアルタイムの生成ステータス表示
- 自動ポーリングによる進捗確認
- 生成されたビデオの即時プレビュー
- レスポンシブデザイン

## 注意事項

- APIキーが必要です
- ビデオ生成には時間がかかります（数分程度）
- 生成されたビデオは`static/`フォルダに保存されます
- API使用料金が発生します

