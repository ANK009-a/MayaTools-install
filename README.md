# MayaTools インストーラ（公開ブートストラップ）

Maya 用ツール群 **MayaTools** を、この PC の Maya に導入し、以後**自動で最新に保つ**ためのインストーラです。

> このリポジトリに**秘密情報は含まれていません**。ツール本体は別の private リポジトリにあり、
> **トークン**で保護されています（トークンはこのファイルには入っていません）。

## 使い方（Maya で1回だけ）

1. Maya を起動し、**Script Editor の Python タブ**を開く。
2. 管理者から渡された **1 行**を貼り付けて実行（▶ または Ctrl+Enter）:

   ```python
   import urllib.request,base64 as _b; exec(urllib.request.urlopen(_b.b64decode('aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL0FOSzAwOS1hL01heWFUb29scy1pbnN0YWxsL21haW4vaW5zdGFsbC5weQ==').decode()).read().decode('utf-8'))
   ```

3. **インストーラの窓**が開きます。
   - **GitHub Token**: 管理者から渡されたトークンを貼り付け（空のままなら既存設定を温存）
   - **置き場**: そのままでOK（既定 `~/dev/MayaTools`）
   - **［インストール］** を押す
4. ログに **「✓ 完了」** が出たら **Maya を再起動**。

これで完了です。以後はツールが**起動のたびに自動更新**されます（手動作業は不要）。

## うまくいかない時

- 窓が出ない／赤いエラーが出る → **ログの内容**を管理者に伝えてください。
- トークンが分からない → 管理者に確認してください（このインストーラには含まれていません）。

---

<sub>（管理者向け）`install.py` は private の `MayaTools` リポジトリで `deploy/build_installer.py` が生成した
ものの公開ミラーです。`install.py` を変更したら、生成し直してこのリポジトリへ push してください
（push 前に `TOKEN = ""` を確認）。ワンライナーの base64 は生 URL を貼り付けテキストに出さないための
見た目の処理で、秘匿ではありません（復号/通信で見えます）。</sub>
