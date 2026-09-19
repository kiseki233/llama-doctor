# llama-doctor

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

**インストール済みの llama.cpp build に対して、コマンドを検査・診断・移行するツールです。**

`llama-doctor` は、選択した `llama-server` または `llama-cli` 実行ファイルを直接調べ、その `--help` 出力からフラグスキーマを作成し、その build に対してコマンドを検証します。

このプロジェクトは意図的に範囲を限定しています。**コマンドリンター + 移行アシスタント**であり、モデルランチャーや性能最適化ツールではありません。

## 言語

デスクトップ GUI は次の3言語に対応しています。

- English
- 简体中文
- 日本語

GUI は可能な場合システム言語に合わせて起動し、最後に選択した言語を保存します。

CLI はコマンドごとに出力言語を指定できます。

```bash
llama-doctor check --lang en ...
llama-doctor check --lang zh ...
llama-doctor check --lang ja ...
```

既存スクリプトとの互換性を保つため、CLI の既定言語は英語です。`UNKNOWN_FLAG` や `MISSING_VALUE` などの診断 `code` は言語に依存せず、常に同じ値を維持します。

## バージョンと互換性

バージョン番号には、実際に検証した llama.cpp の基準 build が含まれます。

```text
llama-doctor  0.3.1.10731
                ^     ^
                |     llama.cpp build 番号
                llama.cpp バージョン基準
```

これは**他の build が非対応という意味ではありません**。フラグスキーマは常に現在選択した実行ファイルから読み取ります。末尾の build 番号は、このリリースで実際に検証した上流基準を示します。

現在の基準：

```text
llama.cpp 0.3.0-dev (build 10731)
```

## 主な機能

- 選択した実行ファイルを `--version` / `--help` で調査
- その llama.cpp build 専用のフラグスキーマを動的生成
- `-h,    --help, --usage` のような空白を含むエイリアス形式に対応
- 必須値、任意値、列挙値、明示的な数値範囲、基本数値型に対応
- CMD / PowerShell / Bash の一般的な複数行コマンドに対応
- 引用符付き Unicode パスに対応
- 不明なフラグを検出し、近い候補を提示
- 値不足・不要な値を検出
- 基本的な integer / float / enum エラーを検出
- 真の alias と `--perf / --no-perf` のような正負スイッチを区別
- 重複フラグ、alias 重複、正負スイッチ競合を検出
- コマンド内の実行ファイル名と選択した build が異なる場合に警告
- llama.cpp help に環境変数が表示される場合、CLI 値との重複を報告
- help から `(DEPRECATED)` を直接検出
- 既知の非推奨・移行済みフラグを報告
- 複数形式の help テキストから enum 候補を抽出
- 削除済み旧フラグは移行完了までエラー扱い
- 明示的に safe と確認された移行のみ自動適用
- 複数旧フラグが同じ新フラグに集約される曖昧なケースでは自動移行しない
- Fix 後に再検証
- alias を正規の長いフラグへ正規化
- JSON 診断と安定した exit code
- 解析済みスキーマをローカルキャッシュ
- Typer/Rich CLI と PySide6 GUI
- 英語・簡体字中国語・日本語の表示に対応

## 意図的に対象外としている機能

現在は次を行いません。

- モデルのダウンロード
- モデル管理
- Chat UI
- Benchmark
- VRAM 最適化
- 自動性能チューニング

つまり：

```text
doctor != optimizer
```

## 開発用インストール

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -e .

# デスクトップ GUI も使う場合
pip install -e ".[gui]"
```

Linux / macOS：

```bash
source .venv/bin/activate
```

## CLI

コマンドを検証：

```bash
llama-doctor check --exe "C:\AI\llama.cpp\llama-server.exe" "llama-server.exe -m model.gguf -c 32768"
```

中国語出力：

```bash
llama-doctor check --lang zh --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

日本語出力：

```bash
llama-doctor check --lang ja --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

stdin から読み込み：

```bash
echo "./llama-server -m model.gguf -c 32768" | llama-doctor check --exe ./llama-server -
```

JSON 診断：

```bash
llama-doctor check --json --lang ja --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

解析したスキーマを表示：

```bash
llama-doctor probe --exe ./llama-server
llama-doctor probe --json --exe ./llama-server
```

alias を正規化：

```bash
llama-doctor normalize --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

安全な移行を適用：

```bash
llama-doctor fix --exe ./llama-server "./llama-server --no-mmap -m model.gguf"
```

キャッシュを使わず再度 `--help` を解析：

```bash
llama-doctor check --no-cache --exe ./llama-server "./llama-server -m model.gguf"
```

### Exit code

| Code | 意味 |
| ---: | --- |
| `0` | 検証エラーなし |
| `1` | 検証 / 解析エラー、未解決の修正、または手動確認が必要 |
| `2` | llama-doctor 内部エラー |
| `3` | 実行ファイルの解析に失敗 |

## GUI

```bash
pip install -e ".[gui]"
llama-doctor-gui
```

基本操作：

1. English / 中文 / 日本語 を選択。
2. `llama-server` または `llama-cli` を選択。
3. 実行ファイルを解析。
4. コマンドを貼り付け。
5. **解析** をクリック。
6. 診断結果を確認。
7. 必要に応じて **コマンド修正** または **正規化** を使用。

## 仕組み

選択した実行ファイル自身の `--help` 出力を主な情報源として使用します。`llama-doctor` は、llama.cpp の更新を追い続ける巨大な固定フラグデータベースを持つ設計ではありません。

静的ルールは、`--help` だけでは安定して推測できない内容に限定しています。

例：

- 既知のフラグ移行
- 危険な旧フラグ組み合わせ

解析済みスキーマは、実行ファイルのパス・サイズ・更新時刻などを使ってキャッシュされます。キャッシュ先は次の環境変数で変更できます。

```text
LLAMA_DOCTOR_CACHE_DIR
```

## 移行の安全性

migration rule が safe とされていても、コマンド全体として結果が曖昧な場合は自動適用しません。

たとえば複数の旧 mmap/mlock フラグが、現在の単一 `--load-mode` に集約される場合があります。複数の旧引数が同じ移行先へ影響する場合、元のフラグを保持して **確認が必要** と表示し、推測で変更しません。

## テスト

```bash
python -m pytest -q
```

現在の多言語版は **89 テスト**です。既存の parser / validator / cache テストに加え、次を追加しています。

- 言語コード正規化
- 中国語 / 日本語の診断表示
- ローカライズ JSON
- 中国語 CLI
- 日本語 CLI
- 英語既定動作の後方互換性

## Windows 実行ファイル

PyInstaller 用スクリプトが含まれています。

```powershell
./scripts/build_windows.ps1
```

出力先は `dist/` です。`v*` tag の GitHub push では付属の release workflow も実行されます。

## 重要な制限

- Shell parser は保守的で、CMD / PowerShell / Bash を完全には再現しません。
- 現在は1回につき1つの llama.cpp コマンドを検証します。
- `--help` からの型推論は誤検出を避けるため意図的に保守的です。
- Migration rule は上流の挙動が文書化または検証済みの場合にのみ追加すべきです。
- GUI 実行にはオプション依存関係 PySide6 が必要です。

## プライバシー

検証はすべてローカルで行われます。`llama-doctor` はコマンドやモデルをアップロードせず、ネットワーク接続も必要としません。

## License

MIT
