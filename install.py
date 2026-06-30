# -*- coding: utf-8 -*-
"""
install.py — MayaTools「受け取り役 (bootstrap)」を、このPCの Maya に 1 回だけ設置する。

※ このファイルは deploy/build_installer.py が自動生成したもの。手で編集しないこと
  (直すなら deploy/bootstrap/ 側を直して build_installer.py を再実行)。

== 使い方 ==
  Maya の Script Editor (Python タブ) にこのファイル全体を貼り付けて実行すると、
  インストーラのウィンドウが開く。GitHub トークンと置き場を入れて [インストール] を押すだけ。
  完了したら Maya を再起動。以後は起動するたび自動で最新になる。
  (シェルフに登録しておけば、次回からはボタン 1 つでこの窓を開ける)

  ※ 下の「ADMIN 既定値」は UI の初期値。GUI が無い環境 (バッチ等) ではこの値のまま headless 実行。

やること (インストール時):
  * 置き場 (CACHE_DIR) の中に bootstrap(更新役) + .mod + config.json を配置 (一か所集約)
  * config.json を生成 (TOKEN 未指定なら既存 token を温存)
  * Maya.env の MAYA_MODULE_PATH に <cache> と <cache>/live を設定
    (置き場を変えた場合は旧置き場の登録を除去 = クリーン移転)
  * (トークンがあれば) 初回同期を 1 回その場で実行してツール本体を取得
"""
import base64
import json
import os
import sys

# ===================== ADMIN 既定値 (UI の初期値・任意で編集) =====================
# UI で入力するので普段は編集不要。バッチ等 GUI 無し環境ではこの値のまま headless 実行する。
TOKEN = ""                    # GitHub fine-grained PAT (Contents: Read-only, 対象repoのみ)
                              #   空のまま再実行すると、既存 config.json の token を温存する
OWNER = "ANK009-a"           # GitHub オーナー
REPO = "MayaTools-dist"      # 配布repo (難読化ビルドの Release)。動作確認だけなら "MayaTools"
SOURCE_MODE = "release"      # "release"(最新Release) or "zipball"(任意ref直引き=動作確認用)
REF = "main"                 # SOURCE_MODE=zipball のとき取得する branch/tag
CACHE_DIR = ""               # ツール本体の置き場。空=%LOCALAPPDATA%\MayaTools。
                              #   例: "~/dev/MayaTools" (おすすめ) / "C:/Users/xxx/dev/MayaTools"
                              #   ※ パスは / で書くこと。\ を使うなら r"C:\...\dev" と raw 文字列に。
                              #     普通の "C:\Users\..." は \U エラー(unicodeescape)になる。
                              #   (~ や %VAR% は各PCで展開される。中に current/ 等が作られる)
CHECK_INTERVAL_HOURS = 0     # 更新確認の最短間隔(時間)。0=毎起動
RUN_INITIAL_SYNC = True      # インストール時にその場で初回ダウンロードする
# ============================================================================

_BOOT_FILES = {
    'userSetup.py': (
        'IyAtKi0gY29kaW5nOiB1dGYtOCAtKi0KIiIiCnVzZXJTZXR1cC5weSAoTWF5YVRvb2xzQm9vdHN0'
        'cmFwKSDigJQg5ZCEUEPjgasx5Zue44Gg44GR572u44GP44CM5Y+X44GR5Y+W44KK5b2544CN44Gu'
        '6LW35YuV44OV44OD44Kv44CCCgpNYXlhIOi1t+WLleaZguOBq+OBk+OBruODleOCoeOCpOODq+OB'
        'jOWun+ihjOOBleOCjOOAgeWQjOODleOCqeODq+ODgOOBriBtYXlhdG9vbHNfdXBkYXRlci5ydW4o'
        'KSDjgpLlkbzjgbbjgIIK44KE44KL44GT44Go44Gv44CM5YmN5ZueIERMIOa4iOOBv+OBrueJiOOC'
        'kiBjdXJyZW50IOOBq+aYh+agvCArIOaWsOeJiOOCkuODkOODg+OCr+OCsOODqeOCpuODs+ODieWP'
        'luW+l+OAjeOBoOOBkeOAggrjg4Tjg7zjg6vmnKzkvZMgKOODoeODi+ODpeODvOani+evieODu+WQ'
        'hOODhOODvOODq+i1t+WLlSkg44GvIGN1cnJlbnQvTWF5YVRvb2xzLm1vZCDlgbTjga4gdXNlclNl'
        'dHVwLnB5IOOBjOaLheOBhgrjga7jgafjgIHjgZPjgZPjga/mm7TmlrDjgaDjgZHjgavlvrnjgZnj'
        'gosgKD0g5pys5L2T44Go55aO57WQ5ZCI44O75pys5L2T44GM56m644Gn44KC5aOK44KM44Gq44GE'
        'KeOAggoK5rOo5oSPOgogICog44GT44KM44Gv44CM44OE44O844Or5pys5L2T5YG044CN44GuIHNj'
        'cmlwdHMvdXNlclNldHVwLnB5IOOBqOOBr+WIpeeJqeOAgk1heWEg44GvIFBZVEhPTlBBVEgg5LiK'
        '44GuCiAgICDlkITjg5Xjgqnjg6vjg4Djga4gdXNlclNldHVwLnB5IOOCkuWun+ihjOOBmeOCi+OB'
        'ruOBp+S4oeaWuei1sOOCiyAoPSDmm7TmlrDlvbkgKyDmnKzkvZPjg6Hjg4vjg6Xjg7wp44CCCiAg'
        'KiBhcHBseSDjga8gcnVuKCkg5YaF44Gn5ZCM5pyf5a6f6KGMICg9IGRlZmVycmVkIOOBruODoeOD'
        'i+ODpeODvOani+evieOCiOOCiuWJjeOBqyBjdXJyZW50IOOBjOeiuuWumuOBmeOCiynjgIIKIiIi'
        'CmltcG9ydCBvcwppbXBvcnQgc3lzCmltcG9ydCB0cmFjZWJhY2sKCgpkZWYgX2Jvb3RfbWF5YXRv'
        'b2xzX3VwZGF0ZXIoKToKICAgIHRyeToKICAgICAgICBoZXJlID0gb3MucGF0aC5kaXJuYW1lKG9z'
        'LnBhdGguYWJzcGF0aChfX2ZpbGVfXykpCiAgICAgICAgaWYgaGVyZSBub3QgaW4gc3lzLnBhdGg6'
        'CiAgICAgICAgICAgIHN5cy5wYXRoLmluc2VydCgwLCBoZXJlKQogICAgICAgIGltcG9ydCBtYXlh'
        'dG9vbHNfdXBkYXRlcgogICAgICAgIG1heWF0b29sc191cGRhdGVyLnJ1bihvcy5wYXRoLmpvaW4o'
        'aGVyZSwgImNvbmZpZy5qc29uIikpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHRyeToK'
        'ICAgICAgICAgICAgZnJvbSBtYXlhLmFwaS5PcGVuTWF5YSBpbXBvcnQgTUdsb2JhbAogICAgICAg'
        'ICAgICBNR2xvYmFsLmRpc3BsYXlXYXJuaW5nKAogICAgICAgICAgICAgICAgIltNYXlhVG9vbHNd'
        'IOiHquWLleabtOaWsOOBrui1t+WLleOBq+WkseaVlzpcbiIgKyB0cmFjZWJhY2suZm9ybWF0X2V4'
        'YygpCiAgICAgICAgICAgICkKICAgICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgICAgICBw'
        'YXNzCgoKIyDlpJrph43lrp/ooYzjgqzjg7zjg4k6IE1heWEg44GvIDEg44K744OD44K344On44Oz'
        '5Lit44GrIHVzZXJTZXR1cC5weSDjgpLopIfmlbDlm57mtYHjgZnjgZPjgajjgYzjgYLjgovjgIIK'
        'aWYgbm90IGdldGF0dHIoc3lzLCAiX21heWF0b29sc191cGRhdGVyX2Jvb3RlZCIsIEZhbHNlKToK'
        'ICAgIHN5cy5fbWF5YXRvb2xzX3VwZGF0ZXJfYm9vdGVkID0gVHJ1ZQogICAgX2Jvb3RfbWF5YXRv'
        'b2xzX3VwZGF0ZXIoKQo='
    ),
    'mayatools_updater.py': (
        'ciIiIgptYXlhdG9vbHNfdXBkYXRlci5weSDigJQgTWF5YVRvb2xzIOiHquWLleabtOaWsOOCqOOD'
        's+OCuOODsyAoc3RkbGliIOOBruOBvyAvIGdpdOODu3BpcCDkuI3opoEpCgo9PSDlvbnlibIgPT0K'
        'ICBHaXRIdWIg44GuIHByaXZhdGUg44Oq44Od44K444OI44Oq44GL44KJ44CM44OE44O844Or5pys'
        '5L2T5LiA5byPICg9IE1heWFUb29scy5tb2Qg44KS5ZCr44KA44OE44Oq44O8KeOAjeOCkgogIEhU'
        'VFBTIOOBp+WPluW+l+OBl+OAgeODreODvOOCq+ODq+OCreODo+ODg+OCt+ODpeOBq+WxlemWi+OB'
        'meOCi+OAgk1heWEg6LW35YuV44GU44Go44GrIGJvb3RzdHJhcCDjgYvjgokgcnVuKCkg44GMCiAg'
        '5ZG844Gw44KM44CBKDEpIOWPluW+l+a4iOOBv+OBruaWsOeJiOOBjOOBguOCjOOBsCBsaXZlIOOC'
        'kuiyvOOCiuabv+OBiCAoMikg44Oq44Oi44O844OI44Gr5paw54mI44GM44GC44KM44Gw5Y+W5b6X'
        '44CB44KS5Zue44GZ44CCCgo9PSDjgq3jg6Pjg4Pjgrfjg6Xmp4vmiJAgKGp1bmN0aW9uIOaWueW8'
        'jykgPT0KICA8Y2FjaGU+LwogICAgdmVyc2lvbnMvPHRhZz4vICAg4oaQIOeJiOOBlOOBqOOBq+WI'
        'peODleOCqeODq+ODgCAoTWF5YVRvb2xzLm1vZCArIHRvb2xzLy4uLikKICAgIGxpdmUgICAgICAg'
        'ICAgICAgIOKGkCBqdW5jdGlvbuOAgnZlcnNpb25zLzxhY3RpdmU+IOOCkuaMh+OBmeOAgk1heWEu'
        'ZW52IOOBjOaMh+OBmeOBruOBr+OBk+OCjCAo5Zu65a6aKQogICAgdG1wLyAgICAgICAgICAgICAg'
        '4oaQIERML+WxlemWi+OCueOCr+ODqeODg+ODgQogICAgc3RhdGUuanNvbiAgICAgICAg4oaQIHsi'
        'YWN0aXZlIjogPHRhZz4sICJwZW5kaW5nIjogPHRhZ3xudWxsPiwgImxhc3RfY2hlY2siOiA8ZXBv'
        'Y2g+fQogICAgdXBkYXRlLmxvZwoKPT0g44Gq44GcIGp1bmN0aW9uIOOBiyAo6YeN6KaB44O76YGO'
        '5Y6744Gu6Ie05ZG944OQ44KwKSA9PQogIOS7peWJjeOBryBgY3VycmVudGAg44OV44Kp44Or44OA'
        '5YWo5L2T44KSIG9zLnJlbmFtZSDjgZfjgablt67jgZfmm7/jgYjjgabjgYTjgZ/jgYzjgIHotbfl'
        'i5XmmYLjgasgTWF5YSDjgYwKICBjdXJyZW50IOWGheOBriBuYXRpdmUgbW9kdWxlICh2ZW5kb3Iv'
        'bnVtcHkvKi5weWQg44KSIGNjcCDoh6rli5Xjg63jg7zjg4njgafjgIFBbmltZUJnVG9vbiDjga4K'
        'ICBkbGwg44KSIEFybm9sZCDjgacpIOOCkioq6ZaL44GE44Gm44Ot44OD44KvKirjgZnjgovjgZ/j'
        'goHjgIEqKldpbmRvd3Mg44GvIHJlbmFtZSDjgpIgV2luRXJyb3IgNSDjgafmi5LlkKYqKuOBl+OA'
        'gQogIOabtOaWsOOBjOawuOS5heOBq+OAjOasoeWbnui1t+WLleOBq+W7tuacn+OAjeOBleOCjOOB'
        'puS4gOWIh+mBqeeUqOOBleOCjOOBquOBj+OBquOBo+OBn+OAggogIOKGkiDniYjjgpIgdmVyc2lv'
        'bnMvPHRhZz4vIOOBq+WIhuOBkeOAgWxpdmUg44KSICoqanVuY3Rpb24gKOODquODs+OCrykqKiDj'
        'gavjgZfjgabosrzjgormm7/jgYjjgovjgIIKICAgIOODquODs+OCr+OBruWJiumZpOKGkuWGjeS9'
        'nOaIkOOBryoq44K/44O844Ky44OD44OI5YaF44GuIGxvY2tlZCDjg5XjgqHjgqTjg6vjgavop6bj'
        'gozjgarjgYQqKuOBruOBp+W4uOOBq+aIkOWKn+OBmeOCi+OAggoKPT0g6Kit6KiI5LiK44Gu6KaB'
        '54K5ID09CiAgKiBhcHBseSAobGl2ZSDosrzmm78pIOOBryBydW4oKSDlhpLpoK3jga4gbWFpbiB0'
        'aHJlYWTjgIJqdW5jdGlvbiDmk43kvZzjgarjga7jgacgbG9ja2VkIOOBp+OCguaIkOWKn+OAggog'
        'ICog44Oq44Oi44O844OI56K66KqNICsg44OA44Km44Oz44Ot44O844OJ44GvIGRhZW1vbiB0aHJl'
        'YWQgKE1heWEvUXQgQVBJIOOBr+inpuOCieOBquOBhCnjgILotbfli5XjgpLjg5bjg63jg4Pjgq/j'
        'gZfjgarjgYTjgIIKICAqIHByaXZhdGUgcmVwbyDlr77lv5w6IDMwMiDjgacgY29kZWxvYWQvUzMg'
        '44Gr6aOb44G25YWI44G4IEF1dGhvcml6YXRpb24g44KS6YCB44KJ44Gq44GE44CCCiAgKiBXaW5k'
        'b3dzIE1BWF9QQVRIIOWvvuetljog5bGV6ZaLL+enu+WLleOBryBcXD9cIOmVt+ODkeOCueOBp+ih'
        'jOOBhuOAggogICog54mI44OV44Kp44Or44OA44GvIGJlc3QtZWZmb3J0IOaOg+mZpCAobG9ja2Vk'
        'IOOBr+asoeWbnuWbnuOBlynjgIJNYXlhLmVudiDjga8gbGl2ZSDlm7rlrprjgarjga7jgafop6bj'
        'gonjgarjgYTjgIIKIiIiCmZyb20gX19mdXR1cmVfXyBpbXBvcnQgYW5ub3RhdGlvbnMKCmltcG9y'
        'dCBqc29uCmltcG9ydCBvcwppbXBvcnQgc2h1dGlsCmltcG9ydCBzdWJwcm9jZXNzCmltcG9ydCB0'
        'aHJlYWRpbmcKaW1wb3J0IHRpbWUKaW1wb3J0IHRyYWNlYmFjawppbXBvcnQgdXJsbGliLmVycm9y'
        'CmltcG9ydCB1cmxsaWIucGFyc2UKaW1wb3J0IHVybGxpYi5yZXF1ZXN0CmltcG9ydCB6aXBmaWxl'
        'CgojIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLQojIOWumuaVsAojIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLQpBUElf'
        'Uk9PVCA9ICJodHRwczovL2FwaS5naXRodWIuY29tIgpVU0VSX0FHRU5UID0gIk1heWFUb29scy11'
        'cGRhdGVyIgpET1dOTE9BRF9USU1FT1VUID0gMTgwCkFQSV9USU1FT1VUID0gMjAKU0VOVElORUwg'
        'PSAiTWF5YVRvb2xzLm1vZCIgICAgICAjIOeJiOOBjOOAjOS4rei6q+OBruOBguOCi+ato+OBl+OB'
        'hOODhOODquODvOOAjeOBi+OBruWIpOWumgpMSVZFID0gImxpdmUiICAgICAgICAgICAgICAgICAg'
        'ICMganVuY3Rpb24g5ZCNIChNYXlhLmVudiDjgYzmjIfjgZkpCktFRVBfUkVDRU5UID0gMyAgICAg'
        'ICAgICAgICAgICAgIyDmrovjgZnniYjjg5Xjgqnjg6vjg4DmlbAgKOWPpOOBhOOCguOBruOBi+OC'
        'ieaOg+mZpCkKCiMgYm9vdHN0cmFwICg9IOOBk+OBriB1cGRhdGVyICsgdXNlclNldHVwKSDjga7n'
        'iYjjgIIqKmJvb3RzdHJhcCDjgpLlpInjgYjjgZ/jgokgKzEg44GZ44KL44GT44GoKirjgIIKIyBk'
        'aXN0IHBheWxvYWQg44GuIF9ib290c3RyYXAvIOOBq+aWsOOBl+OBhOeJiOOBjOadpeOBpuOBhOOC'
        'jOOBsCBydW4oKSDjgYzoh6rlt7Hmm7TmlrDjgZnjgosgKGluc3RhbGwucHkg5YaN6YWN5biD5LiN'
        '6KaBKeOAggpCT09UU1RSQVBfVkVSU0lPTiA9IDEKCkFDQ0VQVF9BU1NFVCA9ICJhcHBsaWNhdGlv'
        'bi9vY3RldC1zdHJlYW0iCkFDQ0VQVF9BUkNISVZFID0gIiovKiIKCl9MT0dfQ0FDSEUgPSBOb25l'
        'ICAjIHJ1bigpIOOBp+eiuuWumgoKCiMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tCiMg44OR44K5IC8g44Ot'
        '44KwCiMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tCmRlZiBkZWZhdWx0X2NhY2hlX2RpcigpIC0+IHN0cjoK'
        'ICAgIGJhc2UgPSBvcy5lbnZpcm9uLmdldCgiTE9DQUxBUFBEQVRBIikKICAgIGlmIG5vdCBiYXNl'
        'OgogICAgICAgIGJhc2UgPSBvcy5wYXRoLmpvaW4ob3MucGF0aC5leHBhbmR1c2VyKCJ+IiksICIu'
        'bG9jYWwiLCAic2hhcmUiKQogICAgcmV0dXJuIG9zLnBhdGguam9pbihiYXNlLCAiTWF5YVRvb2xz'
        'IikKCgpkZWYgX2xwKHBhdGg6IHN0cikgLT4gc3RyOgogICAgIiIiV2luZG93cyBNQVhfUEFUSCgy'
        'NjApIOWbnumBv+OBrumVt+ODkeOCueODl+ODrOODleOCo+ODg+OCr+OCueOAgiIiIgogICAgaWYg'
        'b3MubmFtZSAhPSAibnQiOgogICAgICAgIHJldHVybiBwYXRoCiAgICBwID0gb3MucGF0aC5hYnNw'
        'YXRoKHBhdGgpCiAgICBpZiBwLnN0YXJ0c3dpdGgoIlxcXFw/XFwiKToKICAgICAgICByZXR1cm4g'
        'cAogICAgaWYgcC5zdGFydHN3aXRoKCJcXFxcIik6CiAgICAgICAgcmV0dXJuICJcXFxcP1xcVU5D'
        'XFwiICsgcFsyOl0KICAgIHJldHVybiAiXFxcXD9cXCIgKyBwCgoKZGVmIF9sb2cobXNnOiBzdHIp'
        'IC0+IE5vbmU6CiAgICB0ZXh0ID0gIltNYXlhVG9vbHNdICIgKyBzdHIobXNnKQogICAgY2FjaGUg'
        'PSBfTE9HX0NBQ0hFIG9yIGRlZmF1bHRfY2FjaGVfZGlyKCkKICAgIHRyeToKICAgICAgICBvcy5t'
        'YWtlZGlycyhjYWNoZSwgZXhpc3Rfb2s9VHJ1ZSkKICAgICAgICB3aXRoIG9wZW4ob3MucGF0aC5q'
        'b2luKGNhY2hlLCAidXBkYXRlLmxvZyIpLCAiYSIsIGVuY29kaW5nPSJ1dGYtOCIpIGFzIGY6CiAg'
        'ICAgICAgICAgIGYud3JpdGUodGltZS5zdHJmdGltZSgiJVktJW0tJWQgJUg6JU06JVMgIikgKyB0'
        'ZXh0ICsgIlxuIikKICAgIGV4Y2VwdCBFeGNlcHRpb246CiAgICAgICAgcGFzcwogICAgdHJ5Ogog'
        'ICAgICAgIGlmIHRocmVhZGluZy5jdXJyZW50X3RocmVhZCgpIGlzIHRocmVhZGluZy5tYWluX3Ro'
        'cmVhZCgpOgogICAgICAgICAgICBmcm9tIG1heWEuYXBpLk9wZW5NYXlhIGltcG9ydCBNR2xvYmFs'
        'ICAjIG5vcWE6IFBMQzA0MTUKICAgICAgICAgICAgTUdsb2JhbC5kaXNwbGF5SW5mbyh0ZXh0KQog'
        'ICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICBwYXNzCgoKIyAtLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0K'
        'IyDoqK3lrpoKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KZGVmIGxvYWRfY29uZmlnKHBhdGg6IHN0ciB8'
        'IE5vbmUgPSBOb25lKSAtPiBkaWN0OgogICAgaWYgcGF0aCBpcyBOb25lOgogICAgICAgIHBhdGgg'
        'PSBvcy5wYXRoLmpvaW4ob3MucGF0aC5kaXJuYW1lKG9zLnBhdGguYWJzcGF0aChfX2ZpbGVfXykp'
        'LCAiY29uZmlnLmpzb24iKQogICAgd2l0aCBvcGVuKHBhdGgsICJyIiwgZW5jb2Rpbmc9InV0Zi04'
        'IikgYXMgZjoKICAgICAgICByZXR1cm4ganNvbi5sb2FkKGYpCgoKIyAtLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0KIyBIVFRQIChwcml2YXRlIHJlcG86IOODm+OCueODiOOBjOWkieOCj+OCiyByZWRpcmVjdCDj'
        'gafjga8gQXV0aG9yaXphdGlvbiDjgpLokL3jgajjgZkpCiMgLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tCmNs'
        'YXNzIF9BdXRoQXdhcmVSZWRpcmVjdCh1cmxsaWIucmVxdWVzdC5IVFRQUmVkaXJlY3RIYW5kbGVy'
        'KToKICAgIGRlZiByZWRpcmVjdF9yZXF1ZXN0KHNlbGYsIHJlcSwgZnAsIGNvZGUsIG1zZywgaGVh'
        'ZGVycywgbmV3dXJsKToKICAgICAgICBuZXcgPSBzdXBlcigpLnJlZGlyZWN0X3JlcXVlc3QocmVx'
        'LCBmcCwgY29kZSwgbXNnLCBoZWFkZXJzLCBuZXd1cmwpCiAgICAgICAgaWYgbmV3IGlzIG5vdCBO'
        'b25lOgogICAgICAgICAgICB0cnk6CiAgICAgICAgICAgICAgICBpZiB1cmxsaWIucGFyc2UudXJs'
        'c3BsaXQocmVxLmZ1bGxfdXJsKS5ob3N0bmFtZSAhPSB1cmxsaWIucGFyc2UudXJsc3BsaXQobmV3'
        'dXJsKS5ob3N0bmFtZToKICAgICAgICAgICAgICAgICAgICBmb3IgayBpbiBsaXN0KG5ldy5oZWFk'
        'ZXJzLmtleXMoKSk6CiAgICAgICAgICAgICAgICAgICAgICAgIGlmIGsubG93ZXIoKSA9PSAiYXV0'
        'aG9yaXphdGlvbiI6CiAgICAgICAgICAgICAgICAgICAgICAgICAgICBkZWwgbmV3LmhlYWRlcnNb'
        'a10KICAgICAgICAgICAgICAgICAgICBuZXcudW5yZWRpcmVjdGVkX2hkcnMucG9wKCJBdXRob3Jp'
        'emF0aW9uIiwgTm9uZSkKICAgICAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICAgICAg'
        'ICAgIHBhc3MKICAgICAgICByZXR1cm4gbmV3CgoKZGVmIF9vcGVuZXIoKToKICAgIHJldHVybiB1'
        'cmxsaWIucmVxdWVzdC5idWlsZF9vcGVuZXIoX0F1dGhBd2FyZVJlZGlyZWN0KCkpCgoKZGVmIF9y'
        'ZXF1ZXN0KHVybDogc3RyLCB0b2tlbjogc3RyLCBhY2NlcHQ6IHN0cikgLT4gdXJsbGliLnJlcXVl'
        'c3QuUmVxdWVzdDoKICAgIHJlcSA9IHVybGxpYi5yZXF1ZXN0LlJlcXVlc3QodXJsKQogICAgcmVx'
        'LmFkZF9oZWFkZXIoIlVzZXItQWdlbnQiLCBVU0VSX0FHRU5UKQogICAgcmVxLmFkZF9oZWFkZXIo'
        'IkFjY2VwdCIsIGFjY2VwdCkKICAgIGlmIHRva2VuOgogICAgICAgIHJlcS5hZGRfaGVhZGVyKCJB'
        'dXRob3JpemF0aW9uIiwgIkJlYXJlciAiICsgdG9rZW4pCiAgICByZXR1cm4gcmVxCgoKZGVmIF9h'
        'cGlfanNvbih1cmw6IHN0ciwgdG9rZW46IHN0cikgLT4gZGljdDoKICAgIHJlcSA9IF9yZXF1ZXN0'
        'KHVybCwgdG9rZW4sICJhcHBsaWNhdGlvbi92bmQuZ2l0aHViK2pzb24iKQogICAgd2l0aCBfb3Bl'
        'bmVyKCkub3BlbihyZXEsIHRpbWVvdXQ9QVBJX1RJTUVPVVQpIGFzIHI6CiAgICAgICAgcmV0dXJu'
        'IGpzb24ubG9hZHMoci5yZWFkKCkuZGVjb2RlKCJ1dGYtOCIpKQoKCmRlZiBfZG93bmxvYWQodXJs'
        'OiBzdHIsIGRlc3Q6IHN0ciwgdG9rZW46IHN0ciwgYWNjZXB0OiBzdHIpIC0+IE5vbmU6CiAgICAj'
        'IGFjY2VwdCDjga/lj5blvpfnqK7liKXjgaflpInjgYjjgos6IGFzc2V0PW9jdGV0LXN0cmVhbSAv'
        'IHppcGJhbGw9Ki8qIChvY3RldCDjgaDjgaggNDE1KeOAggogICAgcmVxID0gX3JlcXVlc3QodXJs'
        'LCB0b2tlbiwgYWNjZXB0KQogICAgd2l0aCBfb3BlbmVyKCkub3BlbihyZXEsIHRpbWVvdXQ9RE9X'
        'TkxPQURfVElNRU9VVCkgYXMgciwgb3BlbihkZXN0LCAid2IiKSBhcyBmOgogICAgICAgIHNodXRp'
        'bC5jb3B5ZmlsZW9iaihyLCBmLCBsZW5ndGg9MjU2ICogMTAyNCkKCgpkZWYgX2h0dHBfaGludChj'
        'b2RlOiBpbnQpIC0+IHN0cjoKICAgIGlmIGNvZGUgPT0gNDAxOgogICAgICAgIHJldHVybiAi44OI'
        '44O844Kv44Oz44GM54Sh5Yq5L+acn+mZkOWIh+OCjOOBruWPr+iDveaApyAoY29uZmlnLmpzb24g'
        '44GuIHRva2VuIOOCkueiuuiqjSkiCiAgICBpZiBjb2RlID09IDQwMzoKICAgICAgICByZXR1cm4g'
        'KCLmqKnpmZDkuI3otrMgb3Ig44Os44O844OI5Yi26ZmQ44CCZmluZS1ncmFpbmVkIFBBVCDjga4g'
        'UmVwb3NpdG9yeSBhY2Nlc3Mg44Gr5a++6LGhIHJlcG8g44KS5ZCr44KB44CBIgogICAgICAgICAg'
        'ICAgICAgIkNvbnRlbnRzPVJlYWQg44KS5LuY5LiO44GX44Gm44GE44KL44GL56K66KqNIChjbGFz'
        'c2ljIHRva2VuIOOBquOCiSByZXBvIOOCueOCs+ODvOODlykiKQogICAgaWYgY29kZSA9PSA0MDQ6'
        'CiAgICAgICAgcmV0dXJuICJvd25lci9yZXBvL3JlZi9zb3VyY2VfbW9kZSDjgpLnorroqo0gKHBy'
        'aXZhdGUg44GnIHRva2VuIOOBjOOBneOBriByZXBvIOOCkuimi+OCieOCjOOBquOBhOWgtOWQiOOC'
        'giA0MDQpIgogICAgcmV0dXJuICJ0b2tlbi9vd25lci9yZXBvL3NvdXJjZV9tb2RlIOOCkueiuuiq'
        'jSIKCgpkZWYgX3Jlc29sdmVfcmVtb3RlKGNmZzogZGljdCkgLT4gZGljdDoKICAgICIiInsidmVy'
        'c2lvbiIsICJ1cmwiLCAiYWNjZXB0In0g44KS6L+U44GZ44CC5aSx5pWX5pmC44Gv5L6L5aSW44CC'
        'IiIiCiAgICBvd25lciwgcmVwbywgdG9rZW4gPSBjZmdbIm93bmVyIl0sIGNmZ1sicmVwbyJdLCBj'
        'ZmcuZ2V0KCJ0b2tlbiIsICIiKQogICAgbW9kZSA9IGNmZy5nZXQoInNvdXJjZV9tb2RlIiwgInJl'
        'bGVhc2UiKQogICAgaWYgbW9kZSA9PSAicmVsZWFzZSI6CiAgICAgICAgZGF0YSA9IF9hcGlfanNv'
        'bihmIntBUElfUk9PVH0vcmVwb3Mve293bmVyfS97cmVwb30vcmVsZWFzZXMvbGF0ZXN0IiwgdG9r'
        'ZW4pCiAgICAgICAgdmVyc2lvbiA9IGRhdGEuZ2V0KCJ0YWdfbmFtZSIpIG9yIGRhdGEuZ2V0KCJu'
        'YW1lIikgb3IgIiIKICAgICAgICBmb3IgYSBpbiBkYXRhLmdldCgiYXNzZXRzIiwgW10pOgogICAg'
        'ICAgICAgICBpZiBzdHIoYS5nZXQoIm5hbWUiLCAiIikpLmxvd2VyKCkuZW5kc3dpdGgoIi56aXAi'
        'KToKICAgICAgICAgICAgICAgIHJldHVybiB7InZlcnNpb24iOiB2ZXJzaW9uLCAidXJsIjogYVsi'
        'dXJsIl0sICJhY2NlcHQiOiBBQ0NFUFRfQVNTRVR9CiAgICAgICAgcmV0dXJuIHsidmVyc2lvbiI6'
        'IHZlcnNpb24sICJ1cmwiOiBkYXRhWyJ6aXBiYWxsX3VybCJdLCAiYWNjZXB0IjogQUNDRVBUX0FS'
        'Q0hJVkV9CiAgICByZWYgPSBjZmcuZ2V0KCJyZWYiLCAibWFpbiIpCiAgICBkYXRhID0gX2FwaV9q'
        'c29uKGYie0FQSV9ST09UfS9yZXBvcy97b3duZXJ9L3tyZXBvfS9jb21taXRzL3tyZWZ9IiwgdG9r'
        'ZW4pCiAgICByZXR1cm4geyJ2ZXJzaW9uIjogZGF0YVsic2hhIl0sCiAgICAgICAgICAgICJ1cmwi'
        'OiBmIntBUElfUk9PVH0vcmVwb3Mve293bmVyfS97cmVwb30vemlwYmFsbC97cmVmfSIsCiAgICAg'
        'ICAgICAgICJhY2NlcHQiOiBBQ0NFUFRfQVJDSElWRX0KCgojIC0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLQoj'
        'IOOCreODo+ODg+OCt+ODpSAvIOeJiCAvIGp1bmN0aW9uCiMgLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tCmRl'
        'ZiBfc2FmZV90YWcodGFnOiBzdHIpIC0+IHN0cjoKICAgIHJldHVybiAiIi5qb2luKGMgaWYgKGMu'
        'aXNhbG51bSgpIG9yIGMgaW4gIi5fLSIpIGVsc2UgIl8iIGZvciBjIGluIHN0cih0YWcpKQoKCmRl'
        'ZiBfdmVyc2lvbnNfZGlyKGNhY2hlOiBzdHIpIC0+IHN0cjoKICAgIHJldHVybiBvcy5wYXRoLmpv'
        'aW4oY2FjaGUsICJ2ZXJzaW9ucyIpCgoKZGVmIF92ZXJzaW9uX3BhdGgoY2FjaGU6IHN0ciwgdGFn'
        'OiBzdHIpIC0+IHN0cjoKICAgIHJldHVybiBvcy5wYXRoLmpvaW4oX3ZlcnNpb25zX2RpcihjYWNo'
        'ZSksIF9zYWZlX3RhZyh0YWcpKQoKCmRlZiBfbGl2ZV9wYXRoKGNhY2hlOiBzdHIpIC0+IHN0cjoK'
        'ICAgIHJldHVybiBvcy5wYXRoLmpvaW4oY2FjaGUsIExJVkUpCgoKZGVmIF9pc192YWxpZF9wYXls'
        'b2FkKHJvb3Q6IHN0cikgLT4gYm9vbDoKICAgIHJldHVybiBvcy5wYXRoLmlzZmlsZShvcy5wYXRo'
        'LmpvaW4ocm9vdCwgU0VOVElORUwpKQoKCmRlZiBfaXNfbGluayhwYXRoOiBzdHIpIC0+IGJvb2w6'
        'CiAgICAiIiJwYXRoIOOBjCBqdW5jdGlvbi9zeW1saW5rIChyZXBhcnNlIHBvaW50KSDjgYvjgIIi'
        'IiIKICAgIHRyeToKICAgICAgICBpZiBvcy5wYXRoLmlzbGluayhwYXRoKToKICAgICAgICAgICAg'
        'cmV0dXJuIFRydWUKICAgICAgICByZXR1cm4gb3MucGF0aC5pc2RpcihwYXRoKSBhbmQgYm9vbChn'
        'ZXRhdHRyKG9zLmxzdGF0KHBhdGgpLCAic3RfcmVwYXJzZV90YWciLCAwKSkKICAgIGV4Y2VwdCBP'
        'U0Vycm9yOgogICAgICAgIHJldHVybiBGYWxzZQoKCmRlZiBfcmVtb3ZlX2xpbmsocGF0aDogc3Ry'
        'KSAtPiBOb25lOgogICAgIiIianVuY3Rpb24vc3ltbGluayDjgpLjgIHjgr/jg7zjgrLjg4Pjg4jj'
        'gavop6bjgozjgZrjgavlpJbjgZnjgIIiIiIKICAgIGlmIG5vdCBvcy5wYXRoLmxleGlzdHMocGF0'
        'aCk6CiAgICAgICAgcmV0dXJuCiAgICB0cnk6CiAgICAgICAgb3Mucm1kaXIocGF0aCkgICAgICAg'
        'ICMganVuY3Rpb24g44Gv44GT44KM44Gn5aSW44KM44KLICjjgr/jg7zjgrLjg4Pjg4jjga7kuK3o'
        'uqvjga/mtojjgYjjgarjgYQpCiAgICBleGNlcHQgT1NFcnJvcjoKICAgICAgICB0cnk6CiAgICAg'
        'ICAgICAgIG9zLnVubGluayhwYXRoKQogICAgICAgIGV4Y2VwdCBPU0Vycm9yOgogICAgICAgICAg'
        'ICBwYXNzCgoKZGVmIF9tYWtlX2p1bmN0aW9uKGxpbms6IHN0ciwgdGFyZ2V0OiBzdHIpIC0+IE5v'
        'bmU6CiAgICAiIiJsaW5rIOOCkiBqdW5jdGlvbiDjgajjgZfjgaYgdGFyZ2V0IOOBq+WQkeOBkeOC'
        'iyAo5pei5a2YIGxpbmsg44Gv5aSW44GZKeOAgmxvY2tlZCDjgafjgoLmiJDlip/jgIIiIiIKICAg'
        'IGlmIG9zLm5hbWUgPT0gIm50IjoKICAgICAgICAjIGNtZCDjga4gbWtsaW5rIOOBryBiYWNrc2xh'
        'c2gg5b+F6aCI44CCIkM6L1VzZXJzLy4uLiIg44Gg44GoIC9Vc2VycyDjgpLjgrnjgqTjg4Pjg4Hj'
        'gajoqqToqo3jgZnjgovjgIIKICAgICAgICBsaW5rID0gb3MucGF0aC5ub3JtcGF0aChsaW5rKQog'
        'ICAgICAgIHRhcmdldCA9IG9zLnBhdGgubm9ybXBhdGgodGFyZ2V0KQogICAgX3JlbW92ZV9saW5r'
        'KGxpbmspCiAgICBpZiBvcy5uYW1lID09ICJudCI6CiAgICAgICAgIyBieXRlcyDjgaflj5blvpcg'
        'KGNtZCDjga8gQ1A5MzIg5Ye65Yqb44Gq44Gu44GnIHRleHQ9VHJ1ZSDjgaDjgaggcmVhZGVyIHRo'
        'cmVhZCDjgYwgZGVjb2RlIOS+i+WklikKICAgICAgICByID0gc3VicHJvY2Vzcy5ydW4oWyJjbWQi'
        'LCAiL2MiLCAibWtsaW5rIiwgIi9KIiwgbGluaywgdGFyZ2V0XSwgY2FwdHVyZV9vdXRwdXQ9VHJ1'
        'ZSkKICAgICAgICBpZiByLnJldHVybmNvZGUgIT0gMCBvciBub3Qgb3MucGF0aC5pc2RpcihsaW5r'
        'KToKICAgICAgICAgICAgbXNnID0gKHIuc3RkZXJyIG9yIHIuc3Rkb3V0IG9yIGIiIikuZGVjb2Rl'
        'KCJjcDkzMiIsICJyZXBsYWNlIikuc3RyaXAoKQogICAgICAgICAgICByYWlzZSBPU0Vycm9yKCJq'
        'dW5jdGlvbiDkvZzmiJDlpLHmlZc6ICVzIC0+ICVzIDogJXMiICUgKGxpbmssIHRhcmdldCwgbXNn'
        'KSkKICAgIGVsc2U6CiAgICAgICAgb3Muc3ltbGluayh0YXJnZXQsIGxpbmssIHRhcmdldF9pc19k'
        'aXJlY3Rvcnk9VHJ1ZSkKCgpkZWYgX3JlYWRfc3RhdGUoY2FjaGU6IHN0cikgLT4gZGljdDoKICAg'
        'IHRyeToKICAgICAgICB3aXRoIG9wZW4ob3MucGF0aC5qb2luKGNhY2hlLCAic3RhdGUuanNvbiIp'
        'LCAiciIsIGVuY29kaW5nPSJ1dGYtOCIpIGFzIGY6CiAgICAgICAgICAgIHJldHVybiBqc29uLmxv'
        'YWQoZikKICAgIGV4Y2VwdCBFeGNlcHRpb246CiAgICAgICAgcmV0dXJuIHt9CgoKZGVmIF93cml0'
        'ZV9zdGF0ZShjYWNoZTogc3RyLCBzdGF0ZTogZGljdCkgLT4gTm9uZToKICAgIHRyeToKICAgICAg'
        'ICB3aXRoIG9wZW4ob3MucGF0aC5qb2luKGNhY2hlLCAic3RhdGUuanNvbiIpLCAidyIsIGVuY29k'
        'aW5nPSJ1dGYtOCIpIGFzIGY6CiAgICAgICAgICAgIGpzb24uZHVtcChzdGF0ZSwgZiwgZW5zdXJl'
        'X2FzY2lpPUZhbHNlLCBpbmRlbnQ9MikKICAgIGV4Y2VwdCBFeGNlcHRpb246CiAgICAgICAgX2xv'
        'Zygic3RhdGUuanNvbiDmm7jovrzlpLHmlZc6XG4iICsgdHJhY2ViYWNrLmZvcm1hdF9leGMoKSkK'
        'CgpkZWYgX2ZsYXR0ZW5fc2luZ2xlX3RvcChleHRyYWN0X2Rpcjogc3RyKSAtPiBzdHI6CiAgICBl'
        'bnRyaWVzID0gb3MubGlzdGRpcihleHRyYWN0X2RpcikKICAgIGlmIGxlbihlbnRyaWVzKSA9PSAx'
        'OgogICAgICAgIGlubmVyID0gb3MucGF0aC5qb2luKGV4dHJhY3RfZGlyLCBlbnRyaWVzWzBdKQog'
        'ICAgICAgIGlmIG9zLnBhdGguaXNkaXIoaW5uZXIpOgogICAgICAgICAgICByZXR1cm4gaW5uZXIK'
        'ICAgIHJldHVybiBleHRyYWN0X2RpcgoKCmRlZiBfY2xlYW51cF92ZXJzaW9ucyhjYWNoZTogc3Ry'
        'LCBhbHdheXNfa2VlcCkgLT4gTm9uZToKICAgICIiIueJiOODleOCqeODq+ODgOOCkuWPpOOBhOOC'
        'guOBruOBi+OCieaOg+mZpCAoS0VFUF9SRUNFTlQg5Lu2ICsgYWx3YXlzX2tlZXAg44Gv5q6L44GZ'
        'KeOAgmxvY2tlZCDjga/nhKHoppbjgIIiIiIKICAgIHZkID0gX3ZlcnNpb25zX2RpcihjYWNoZSkK'
        'ICAgIGlmIG5vdCBvcy5wYXRoLmlzZGlyKHZkKToKICAgICAgICByZXR1cm4KICAgIGtlZXAgPSB7'
        'X3NhZmVfdGFnKHQpIGZvciB0IGluIGFsd2F5c19rZWVwIGlmIHR9CiAgICBkaXJzID0gc29ydGVk'
        'KGQgZm9yIGQgaW4gb3MubGlzdGRpcih2ZCkgaWYgb3MucGF0aC5pc2Rpcihvcy5wYXRoLmpvaW4o'
        'dmQsIGQpKSkKICAgICMgdGFnIOOBryBkaXN0LVlZWVlNTURELUhITU1TUyDjgafmmIfpoIY95pmC'
        '57O75YiX44CC5paw44GX44GEIEtFRVBfUkVDRU5UIOS7tuOBr+aui+OBmeOAggogICAgZm9yIGQg'
        'aW4gZGlyc1s6LUtFRVBfUkVDRU5UXSBpZiBsZW4oZGlycykgPiBLRUVQX1JFQ0VOVCBlbHNlIFtd'
        'OgogICAgICAgIGlmIGQgaW4ga2VlcDoKICAgICAgICAgICAgY29udGludWUKICAgICAgICBzaHV0'
        'aWwucm10cmVlKF9scChvcy5wYXRoLmpvaW4odmQsIGQpKSwgaWdub3JlX2Vycm9ycz1UcnVlKQoK'
        'CiMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tCiMg6YGp55SoIChsaXZlIGp1bmN0aW9uIOOBruiyvOabvykg'
        '4oCUIGxvY2tlZCDjgafjgoLmiJDlip8KIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KZGVmIGFwcGx5X3Bl'
        'bmRpbmcoY2FjaGU6IHN0cikgLT4gYm9vbDoKICAgICIiInN0YXRlLnBlbmRpbmcg44GM44GC44KM'
        '44GwIGxpdmUg44KSIHZlcnNpb25zLzxwZW5kaW5nPiDjgbjosrzjgormm7/jgYjjgovjgIIiIiIK'
        'ICAgIHN0YXRlID0gX3JlYWRfc3RhdGUoY2FjaGUpCiAgICBwZW5kaW5nID0gc3RhdGUuZ2V0KCJw'
        'ZW5kaW5nIikKICAgIGlmIG5vdCBwZW5kaW5nOgogICAgICAgIHJldHVybiBGYWxzZQogICAgdnAg'
        'PSBfdmVyc2lvbl9wYXRoKGNhY2hlLCBwZW5kaW5nKQogICAgaWYgbm90IF9pc192YWxpZF9wYXls'
        'b2FkKHZwKToKICAgICAgICBzdGF0ZVsicGVuZGluZyJdID0gTm9uZQogICAgICAgIF93cml0ZV9z'
        'dGF0ZShjYWNoZSwgc3RhdGUpCiAgICAgICAgcmV0dXJuIEZhbHNlCiAgICB0cnk6CiAgICAgICAg'
        'X21ha2VfanVuY3Rpb24oX2xpdmVfcGF0aChjYWNoZSksIHZwKQogICAgZXhjZXB0IE9TRXJyb3Ig'
        'YXMgZToKICAgICAgICBfbG9nKCJsaXZlIOWIh+abv+OBq+WkseaVlyAo5qyh5Zue5YaN6Kmm6KGM'
        'KTogJXMiICUgZSkKICAgICAgICByZXR1cm4gRmFsc2UKICAgIHN0YXRlWyJhY3RpdmUiXSA9IHBl'
        'bmRpbmcKICAgIHN0YXRlWyJwZW5kaW5nIl0gPSBOb25lCiAgICBfd3JpdGVfc3RhdGUoY2FjaGUs'
        'IHN0YXRlKQogICAgX2xvZygi5pu05paw44KS6YGp55So44GX44G+44GX44GfIChsaXZlIC0+ICVz'
        'KSIgJSBzdHIocGVuZGluZylbOjE2XSkKICAgIHJldHVybiBUcnVlCgoKIyAtLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0KIyBib290c3RyYXAgKHVwZGF0ZXIg6Ieq6LqrKSDjga7oh6rlt7Hmm7TmlrAg4oCUIGlu'
        'c3RhbGwucHkg44KS5YaN6YWN5biD44Gb44Ga44GrIHVwZGF0ZXIg44KS5pu05paw44GZ44KLCiMg'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tCmRlZiBfcGFyc2VfYm9vdHN0cmFwX3ZlcnNpb24ocHlfcGF0aDog'
        'c3RyKToKICAgICIiIuODleOCoeOCpOODq+OBi+OCiSBCT09UU1RSQVBfVkVSU0lPTiDjga7lgKTj'
        'gpLjg4bjgq3jgrnjg4jop6PmnpDjgafoqq3jgoAgKGltcG9ydCDjga/jgZfjgarjgYQp44CCIiIi'
        'CiAgICBpbXBvcnQgcmUKICAgIHRyeToKICAgICAgICB3aXRoIG9wZW4ocHlfcGF0aCwgInIiLCBl'
        'bmNvZGluZz0idXRmLTgiLCBlcnJvcnM9Imlnbm9yZSIpIGFzIGY6CiAgICAgICAgICAgIGZvciBs'
        'aW5lIGluIGY6CiAgICAgICAgICAgICAgICBtID0gcmUubWF0Y2gociJccypCT09UU1RSQVBfVkVS'
        'U0lPTlxzKj1ccyooXGQrKSIsIGxpbmUpCiAgICAgICAgICAgICAgICBpZiBtOgogICAgICAgICAg'
        'ICAgICAgICAgIHJldHVybiBpbnQobS5ncm91cCgxKSkKICAgIGV4Y2VwdCBFeGNlcHRpb246CiAg'
        'ICAgICAgcGFzcwogICAgcmV0dXJuIE5vbmUKCgpkZWYgX3JlZnJlc2hfYm9vdHN0cmFwKGNhY2hl'
        'OiBzdHIpIC0+IE5vbmU6CiAgICAiIiJsaXZlICjpgannlKjmuIjjga7niYgpIOOBq+WQjOaiseOB'
        'leOCjOOBn+aWsOOBl+OBhCBib290c3RyYXAg44GM44GC44KM44GwIHVwZGF0ZXIg44KS6Ieq5bex'
        '5pu05paw44GZ44KL44CCCgogICAgZGlzdCBwYXlsb2FkIOOBriBgX2Jvb3RzdHJhcC9gIChtYXlh'
        'dG9vbHNfdXBkYXRlci5weSArIHVzZXJTZXR1cC5weSkg44GuIEJPT1RTVFJBUF9WRVJTSU9OIOOB'
        'jAogICAg6LWw6KGM5Lit44KI44KK5paw44GX44GR44KM44GwIDxjYWNoZT4vYm9vdHN0cmFwLyDj'
        'gavjgrPjg5Tjg7wg4oaSICoq5qyh5ZueIE1heWEg6LW35YuV44Gn5Y+N5pigKirjgILjgZPjgozj'
        'gavjgojjgooKICAgIHVwZGF0ZXIg44Gu44OQ44Kw5L+u5q2j562J44KS44CMaW5zdGFsbC5weSDj'
        'ga7lho3jgrPjg5Tjg5rjgI3jgarjgZfjgaflhaggUEMg44Gr6YWN44KM44KLICg9IOWGjemFjeW4'
        'g+S4jeimgSnjgIIKICAgICAgKiBjb25maWcuanNvbiDjga/op6bjgonjgarjgYQgKHRva2VuIOOC'
        'kuS/neaMgSnjgIIKICAgICAgKiDlo4rjgozjgZ/niYjjgafoqbDjgoDjga7jgpLpmLLjgZDjgZ/j'
        'goHjgIHlj5bjgorovrzjgoDliY3jgasgY29tcGlsZSDmpJzoqLwgKyDml6LlrZjjgpIgLmJhayDj'
        'gavpgIDpgb/jgIIKICAgICIiIgogICAgc3JjX2RpciA9IG9zLnBhdGguam9pbihfbGl2ZV9wYXRo'
        'KGNhY2hlKSwgIl9ib290c3RyYXAiKQogICAgc3JjX3VwZGF0ZXIgPSBvcy5wYXRoLmpvaW4oc3Jj'
        'X2RpciwgIm1heWF0b29sc191cGRhdGVyLnB5IikKICAgIGlmIG5vdCBvcy5wYXRoLmlzZmlsZShz'
        'cmNfdXBkYXRlcik6CiAgICAgICAgcmV0dXJuCiAgICBidW5kbGVkID0gX3BhcnNlX2Jvb3RzdHJh'
        'cF92ZXJzaW9uKHNyY191cGRhdGVyKQogICAgaWYgYnVuZGxlZCBpcyBOb25lIG9yIGJ1bmRsZWQg'
        'PD0gQk9PVFNUUkFQX1ZFUlNJT046CiAgICAgICAgcmV0dXJuCiAgICB0cnk6CiAgICAgICAgd2l0'
        'aCBvcGVuKHNyY191cGRhdGVyLCAiciIsIGVuY29kaW5nPSJ1dGYtOCIpIGFzIGY6CiAgICAgICAg'
        'ICAgIGNvbXBpbGUoZi5yZWFkKCksIHNyY191cGRhdGVyLCAiZXhlYyIpICAgIyDlo4rjgozjgZ8g'
        'dXBkYXRlciDjgpLlj5bjgorovrzjgb7jgarjgYTkv53pmboKICAgIGV4Y2VwdCBFeGNlcHRpb246'
        'CiAgICAgICAgX2xvZygiYm9vdHN0cmFwIOiHquW3seabtOaWsOOCkuimi+mAgeOCiiAo5pawIHVw'
        'ZGF0ZXIg44GMIGNvbXBpbGUg5LiN5Y+vKTogdiVzIiAlIGJ1bmRsZWQpCiAgICAgICAgcmV0dXJu'
        'CiAgICBkc3RfZGlyID0gb3MucGF0aC5qb2luKGNhY2hlLCAiYm9vdHN0cmFwIikKICAgIG9zLm1h'
        'a2VkaXJzKGRzdF9kaXIsIGV4aXN0X29rPVRydWUpCiAgICBmb3IgbmFtZSBpbiAoIm1heWF0b29s'
        'c191cGRhdGVyLnB5IiwgInVzZXJTZXR1cC5weSIpOgogICAgICAgIHNwID0gb3MucGF0aC5qb2lu'
        'KHNyY19kaXIsIG5hbWUpCiAgICAgICAgaWYgbm90IG9zLnBhdGguaXNmaWxlKHNwKToKICAgICAg'
        'ICAgICAgY29udGludWUKICAgICAgICBkcCA9IG9zLnBhdGguam9pbihkc3RfZGlyLCBuYW1lKQog'
        'ICAgICAgIHRyeToKICAgICAgICAgICAgaWYgb3MucGF0aC5pc2ZpbGUoZHApOgogICAgICAgICAg'
        'ICAgICAgc2h1dGlsLmNvcHkyKGRwLCBkcCArICIuYmFrIikKICAgICAgICAgICAgc2h1dGlsLmNv'
        'cHkyKHNwLCBkcCkKICAgICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgICAgICBfbG9nKCJi'
        'b290c3RyYXAg6Ieq5bex5pu05paw44Gn44Kz44OU44O85aSx5pWXICglcyk6XG4lcyIgJSAobmFt'
        'ZSwgdHJhY2ViYWNrLmZvcm1hdF9leGMoKSkpCiAgICAgICAgICAgIHJldHVybgogICAgX2xvZygi'
        'dXBkYXRlciDjgpLoh6rlt7Hmm7TmlrDjgZfjgb7jgZfjgZ8gKHYlcyAtPiB2JXMp44CC5qyh5Zue'
        'IE1heWEg6LW35YuV44Gn5Y+N5pig44GV44KM44G+44GZ44CCIgogICAgICAgICAlIChCT09UU1RS'
        'QVBfVkVSU0lPTiwgYnVuZGxlZCkpCgoKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KIyDlj5blvpcgKGJh'
        'Y2tncm91bmQgdGhyZWFk44CCTWF5YSBBUEkg44Gv6Kem44KJ44Gq44GEKQojIC0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLQpkZWYgY2hlY2tfYW5kX2Rvd25sb2FkKGNmZzogZGljdCwgY2FjaGU6IHN0cikgLT4g'
        'Tm9uZToKICAgIHJlbW90ZSA9IF9yZXNvbHZlX3JlbW90ZShjZmcpCiAgICB2ZXJzaW9uID0gcmVt'
        'b3RlWyJ2ZXJzaW9uIl0KICAgIHN0YXRlID0gX3JlYWRfc3RhdGUoY2FjaGUpCiAgICBsaXZlID0g'
        'X2xpdmVfcGF0aChjYWNoZSkKICAgIGxpdmVfb2sgPSBfaXNfbGluayhsaXZlKSBhbmQgX2lzX3Zh'
        'bGlkX3BheWxvYWQobGl2ZSkKCiAgICBpZiBsaXZlX29rIGFuZCBzdGF0ZS5nZXQoImFjdGl2ZSIp'
        'ID09IHZlcnNpb24gYW5kIG5vdCBzdGF0ZS5nZXQoInBlbmRpbmciKToKICAgICAgICBfbG9nKCLm'
        'nIDmlrDjgafjgZkgKCVzKSIgJSB2ZXJzaW9uWzoxNl0pCiAgICAgICAgcmV0dXJuCgogICAgdnAg'
        'PSBfdmVyc2lvbl9wYXRoKGNhY2hlLCB2ZXJzaW9uKQogICAgaWYgbm90IF9pc192YWxpZF9wYXls'
        'b2FkKHZwKToKICAgICAgICBfbG9nKCLmlrDjg5Djg7zjgrjjg6fjg7PjgpLlj5blvpfjgZfjgb7j'
        'gZk6ICVzIiAlIHZlcnNpb25bOjE2XSkKICAgICAgICB0bXAgPSBvcy5wYXRoLmpvaW4oY2FjaGUs'
        'ICJ0bXAiKQogICAgICAgIHNodXRpbC5ybXRyZWUoX2xwKHRtcCksIGlnbm9yZV9lcnJvcnM9VHJ1'
        'ZSkKICAgICAgICBvcy5tYWtlZGlycyhfbHAodG1wKSwgZXhpc3Rfb2s9VHJ1ZSkKICAgICAgICB6'
        'aXBwYXRoID0gb3MucGF0aC5qb2luKHRtcCwgImRvd25sb2FkLnppcCIpCiAgICAgICAgX2Rvd25s'
        'b2FkKHJlbW90ZVsidXJsIl0sIHppcHBhdGgsIGNmZy5nZXQoInRva2VuIiwgIiIpLCByZW1vdGUu'
        'Z2V0KCJhY2NlcHQiLCBBQ0NFUFRfQVJDSElWRSkpCiAgICAgICAgd2l0aCB6aXBmaWxlLlppcEZp'
        'bGUoemlwcGF0aCkgYXMgejoKICAgICAgICAgICAgaWYgei50ZXN0emlwKCkgaXMgbm90IE5vbmU6'
        'CiAgICAgICAgICAgICAgICByYWlzZSBSdW50aW1lRXJyb3IoInppcCDnoLTmkI0iKQogICAgICAg'
        'ICAgICBleCA9IG9zLnBhdGguam9pbih0bXAsICJleCIpCiAgICAgICAgICAgIG9zLm1ha2VkaXJz'
        'KF9scChleCksIGV4aXN0X29rPVRydWUpCiAgICAgICAgICAgIHouZXh0cmFjdGFsbChfbHAoZXgp'
        'KQogICAgICAgIHJvb3QgPSBfZmxhdHRlbl9zaW5nbGVfdG9wKGV4KQogICAgICAgIGlmIG5vdCBf'
        'aXNfdmFsaWRfcGF5bG9hZChyb290KToKICAgICAgICAgICAgcmFpc2UgUnVudGltZUVycm9yKCLl'
        'j5blvpfnianjgasgJXMg44GM6KaL44Gk44GL44KK44G+44Gb44KTIiAlIFNFTlRJTkVMKQogICAg'
        'ICAgIG9zLm1ha2VkaXJzKF9scChfdmVyc2lvbnNfZGlyKGNhY2hlKSksIGV4aXN0X29rPVRydWUp'
        'CiAgICAgICAgc2h1dGlsLnJtdHJlZShfbHAodnApLCBpZ25vcmVfZXJyb3JzPVRydWUpCiAgICAg'
        'ICAgc2h1dGlsLm1vdmUoX2xwKHJvb3QpLCBfbHAodnApKQogICAgICAgIHNodXRpbC5ybXRyZWUo'
        'X2xwKHRtcCksIGlnbm9yZV9lcnJvcnM9VHJ1ZSkKICAgICAgICBfbG9nKCLlj5blvpflrozkuoY6'
        'ICVzIiAlIHZlcnNpb25bOjE2XSkKCiAgICAjIOasoeWbnui1t+WLleOBp+WPjeaYoCAocGVuZGlu'
        'ZyDjgavnqY3jgoAp44CC44Gf44Gg44GXIGxpdmUg44GM54Sh44GR44KM44Gw5Y2z6YGp55SoICjl'
        'iJ3lm54p44CCCiAgICBzdGF0ZVsicGVuZGluZyJdID0gdmVyc2lvbgogICAgX3dyaXRlX3N0YXRl'
        'KGNhY2hlLCBzdGF0ZSkKICAgIGlmIG5vdCBsaXZlX29rOgogICAgICAgIGFwcGx5X3BlbmRpbmco'
        'Y2FjaGUpCiAgICBlbHNlOgogICAgICAgIF9sb2coIuasoeWbniBNYXlhIOi1t+WLleOBp+WPjeaY'
        'oOOBleOCjOOBvuOBmTogJXMiICUgdmVyc2lvbls6MTZdKQoKCiMgLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'CiMg44Ko44Oz44OI44Oq44Od44Kk44Oz44OICiMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tCmRlZiBydW4o'
        'Y29uZmlnX3BhdGg6IHN0ciB8IE5vbmUgPSBOb25lLCBibG9ja2luZzogYm9vbCA9IEZhbHNlKSAt'
        'PiBOb25lOgogICAgZ2xvYmFsIF9MT0dfQ0FDSEUKICAgIHRyeToKICAgICAgICBjZmcgPSBsb2Fk'
        'X2NvbmZpZyhjb25maWdfcGF0aCkKICAgIGV4Y2VwdCBFeGNlcHRpb24gYXMgZToKICAgICAgICBf'
        'bG9nKCJjb25maWcuanNvbiDoqq3ovrzlpLHmlZcgKOacqumFjee9rj8pOiAlcyIgJSBlKQogICAg'
        'ICAgIHJldHVybgoKICAgIHJhdyA9IGNmZy5nZXQoImNhY2hlX2RpciIpCiAgICBjYWNoZSA9IG9z'
        'LnBhdGguZXhwYW5kdmFycyhvcy5wYXRoLmV4cGFuZHVzZXIocmF3KSkgaWYgcmF3IGVsc2UgZGVm'
        'YXVsdF9jYWNoZV9kaXIoKQogICAgX0xPR19DQUNIRSA9IGNhY2hlCiAgICB0cnk6CiAgICAgICAg'
        'b3MubWFrZWRpcnMoX3ZlcnNpb25zX2RpcihjYWNoZSksIGV4aXN0X29rPVRydWUpCiAgICBleGNl'
        'cHQgRXhjZXB0aW9uOgogICAgICAgIF9sb2coIuOCreODo+ODg+OCt+ODpeS9nOaIkOWkseaVlzpc'
        'biIgKyB0cmFjZWJhY2suZm9ybWF0X2V4YygpKQogICAgICAgIHJldHVybgoKICAgICMgMSkgcGVu'
        'ZGluZyDjgpIgbGl2ZSDjgavpgannlKggKGp1bmN0aW9uIOiyvOabvyA9IGxvY2tlZCDjgafjgoLm'
        'iJDlip8pCiAgICB0cnk6CiAgICAgICAgYXBwbHlfcGVuZGluZyhjYWNoZSkKICAgIGV4Y2VwdCBF'
        'eGNlcHRpb246CiAgICAgICAgX2xvZygiYXBwbHlfcGVuZGluZyDjgafkvovlpJY6XG4iICsgdHJh'
        'Y2ViYWNrLmZvcm1hdF9leGMoKSkKCiAgICAjIDEuNSkgbGl2ZSDjgavlkIzmorHjgZXjgozjgZ/m'
        'lrDjgZfjgYQgYm9vdHN0cmFwIOOBjOOBguOCjOOBsCB1cGRhdGVyIOOCkuiHquW3seabtOaWsCAo'
        'aW5zdGFsbC5weSDlho3phY3luIPkuI3opoHljJYpCiAgICB0cnk6CiAgICAgICAgX3JlZnJlc2hf'
        'Ym9vdHN0cmFwKGNhY2hlKQogICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICBfbG9nKCJib290'
        'c3RyYXAg6Ieq5bex5pu05paw44Gn5L6L5aSWOlxuIiArIHRyYWNlYmFjay5mb3JtYXRfZXhjKCkp'
        'CgogICAgIyAyKSDlj6TjgYTniYjjg5Xjgqnjg6vjg4DjgpLmjoPpmaQgKGFjdGl2ZS9wZW5kaW5n'
        'IOOBr+aui+OBmSkKICAgIHRyeToKICAgICAgICBzdCA9IF9yZWFkX3N0YXRlKGNhY2hlKQogICAg'
        'ICAgIF9jbGVhbnVwX3ZlcnNpb25zKGNhY2hlLCBhbHdheXNfa2VlcD0oc3QuZ2V0KCJhY3RpdmUi'
        'KSwgc3QuZ2V0KCJwZW5kaW5nIikpKQogICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICBwYXNz'
        'CgogICAgaWYgbm90IGNmZy5nZXQoImVuYWJsZWQiLCBUcnVlKToKICAgICAgICBfbG9nKCLoh6rl'
        'i5Xmm7TmlrDjga/nhKHlirnljJbjgZXjgozjgabjgYTjgb7jgZkgKGNvbmZpZy5lbmFibGVkPWZh'
        'bHNlKSIpCiAgICAgICAgcmV0dXJuCiAgICBpZiBub3QgY2ZnLmdldCgidG9rZW4iKToKICAgICAg'
        'ICBfbG9nKCJ0b2tlbiDmnKroqK3lrprjga7jgZ/jgoHmm7TmlrDjg4Hjgqfjg4Pjgq/jgpLjgrnj'
        'gq3jg4Pjg5cgKGNvbmZpZy5qc29uIOOBqyB0b2tlbiDjgpLoqK3lrpopIikKICAgICAgICByZXR1'
        'cm4KCiAgICBpbnRlcnZhbCA9IGZsb2F0KGNmZy5nZXQoImNoZWNrX2ludGVydmFsX2hvdXJzIiwg'
        'MCkgb3IgMCkgKiAzNjAwLjAKICAgIHN0YXRlID0gX3JlYWRfc3RhdGUoY2FjaGUpCiAgICBpZiBp'
        'bnRlcnZhbCA+IDAgYW5kICh0aW1lLnRpbWUoKSAtIGZsb2F0KHN0YXRlLmdldCgibGFzdF9jaGVj'
        'ayIsIDApKSkgPCBpbnRlcnZhbDoKICAgICAgICBfbG9nKCLjg4Hjgqfjg4Pjgq/plpPpmpTlhoXj'
        'ga7jgZ/jgoHmm7TmlrDnorroqo3jgpLjgrnjgq3jg4Pjg5ciKQogICAgICAgIHJldHVybgoKICAg'
        'IGRlZiB3b3JrZXIoKToKICAgICAgICB0cnk6CiAgICAgICAgICAgIGNoZWNrX2FuZF9kb3dubG9h'
        'ZChjZmcsIGNhY2hlKQogICAgICAgIGV4Y2VwdCB1cmxsaWIuZXJyb3IuSFRUUEVycm9yIGFzIGU6'
        'CiAgICAgICAgICAgIHRyeToKICAgICAgICAgICAgICAgIGJvZHkgPSBlLnJlYWQoKS5kZWNvZGUo'
        'InV0Zi04IiwgInJlcGxhY2UiKS5zdHJpcCgpWzozMDBdCiAgICAgICAgICAgIGV4Y2VwdCBFeGNl'
        'cHRpb246CiAgICAgICAgICAgICAgICBib2R5ID0gIiIKICAgICAgICAgICAgX2xvZygi5pu05paw'
        '44OB44Kn44OD44Kv5aSx5pWXIChIVFRQICVzICVzKS4gJXMlcyIKICAgICAgICAgICAgICAgICAl'
        'IChlLmNvZGUsIGUucmVhc29uLCBfaHR0cF9oaW50KGUuY29kZSksICgiXG4gIEdpdEh1YjogIiAr'
        'IGJvZHkpIGlmIGJvZHkgZWxzZSAiIikpCiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAg'
        'ICAgICAgX2xvZygi5pu05paw44OB44Kn44OD44Kv5aSx5pWXOlxuIiArIHRyYWNlYmFjay5mb3Jt'
        'YXRfZXhjKCkpCiAgICAgICAgZmluYWxseToKICAgICAgICAgICAgc3QyID0gX3JlYWRfc3RhdGUo'
        'Y2FjaGUpCiAgICAgICAgICAgIHN0MlsibGFzdF9jaGVjayJdID0gdGltZS50aW1lKCkKICAgICAg'
        'ICAgICAgX3dyaXRlX3N0YXRlKGNhY2hlLCBzdDIpCgogICAgaWYgYmxvY2tpbmc6CiAgICAgICAg'
        'd29ya2VyKCkKICAgIGVsc2U6CiAgICAgICAgdGhyZWFkaW5nLlRocmVhZCh0YXJnZXQ9d29ya2Vy'
        'LCBuYW1lPSJNYXlhVG9vbHNVcGRhdGVyIiwgZGFlbW9uPVRydWUpLnN0YXJ0KCkK'
    ),
}

_MOD_FILE = {
    'MayaToolsBootstrap.mod': (
        'Ly8gTWF5YVRvb2xzQm9vdHN0cmFwIOKAlCDlkIRQQ+OBqzHlm57jgaDjgZHnva7jgY/jgIzlj5fj'
        'gZHlj5bjgorlvbnjgI3jg6Ljgrjjg6Xjg7zjg6vjgIIKLy8gfi9Eb2N1bWVudHMvbWF5YS9tb2R1'
        'bGVzLyDjgasgTWF5YVRvb2xzQm9vdHN0cmFwLm1vZCAo44GT44Gu44OV44Kh44Kk44OrKSDjgajl'
        'kIzlkI3jg5Xjgqnjg6vjg4AKLy8gTWF5YVRvb2xzQm9vdHN0cmFwLyAodXNlclNldHVwLnB5ICsg'
        'bWF5YXRvb2xzX3VwZGF0ZXIucHkgKyBjb25maWcuanNvbikg44KS572u44GP44CCCi8vIFBZVEhP'
        'TlBBVEgg44Gr6Ieq6Lqr44KS6LyJ44Gb44KL44GT44Go44Gn6LW35YuV5pmCIHVzZXJTZXR1cC5w'
        'eSDjgYzotbDjgorjgIHoh6rli5Xmm7TmlrDjgYzlm57jgovjgIIKLy8g44OE44O844Or5pys5L2T'
        '44Gv5Yil6YCU44Kt44Oj44OD44K344OlICglTE9DQUxBUFBEQVRBJVxNYXlhVG9vbHNcY3VycmVu'
        'dCkg44KSIE1heWEuZW52IOOBrgovLyBNQVlBX01PRFVMRV9QQVRIIOe1jOeUseOBpyBuYXRpdmUg'
        '44Ot44O844OJ44GZ44KLICg9IOOBk+OBruODouOCuOODpeODvOODq+OBr+abtOaWsOOBoOOBkeaL'
        'heW9kynjgIIKKyBNYXlhVG9vbHNCb290c3RyYXAgMS4wIE1heWFUb29sc0Jvb3RzdHJhcApQWVRI'
        'T05QQVRIICs6PSAuCg=='
    ),
}


def _maya_dirs():
    import maya.cmds as cmds
    appdir = cmds.internalVar(userAppDir=True)   # 例: C:/Users/x/Documents/maya/
    version = cmds.about(version=True)            # 例: "2024"
    return appdir, version


def _write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def _expand(p):
    return os.path.expandvars(os.path.expanduser(p)) if p else p


def _norm(p):
    return os.path.normcase(os.path.normpath(p)) if p else None


def _default_cache():
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "MayaTools")


def _set_maya_env_cache(env_path, remove_paths, add_paths):
    """Maya.env の MAYA_MODULE_PATH に add_paths を入れる (冪等)。remove_paths は除去。

    一か所集約レイアウトでは add_paths = [<cache>(bootstrap.mod 用), <cache>/live(ツール本体)]。
    旧レイアウト(current) や旧置き場の登録は remove_paths で消す。ユーザー独自エントリは温存。
    """
    os.makedirs(os.path.dirname(env_path), exist_ok=True)
    add_n = set(_norm(p) for p in add_paths)
    rm_n = set(_norm(p) for p in remove_paths if p) - add_n

    lines = []
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()

    for i, line in enumerate(lines):
        s = line.strip()
        if s.replace(" ", "").upper().startswith("MAYA_MODULE_PATH=") and "=" in s:
            key, _, val = line.partition("=")
            kept = []
            for raw in val.split(os.pathsep):
                p = raw.strip()
                if not p:
                    continue
                pn = _norm(p)
                if pn in add_n or pn in rm_n:
                    continue
                kept.append(p)
            kept.extend(add_paths)
            lines[i] = key + "=" + os.pathsep.join(kept)
            with open(env_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + "\n")
            return "更新"

    lines.append("MAYA_MODULE_PATH=" + os.pathsep.join(add_paths))
    with open(env_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return "新規行を追加"


def _run_install(token, owner, repo, source_mode, ref, cache_dir, run_sync,
                 check_interval_hours=0, log=None):
    """インストール本体。UI からも headless からも呼ばれる。log(msg) で進捗を通知。

    戻り値: dict(ok, cache, env_path, relocated, old_cache, synced, token_set)
    """
    if log is None:
        log = lambda m: None
    appdir, version = _maya_dirs()
    old_modules = os.path.join(appdir, "modules")
    old_boot = os.path.join(old_modules, "MayaToolsBootstrap")   # 集約前の旧 bootstrap 場所

    # 置き場 (cache) を決める。bootstrap も config も versions も live も全部この中にまとめる。
    new_cache = _expand(cache_dir) if cache_dir else _default_cache()
    boot = os.path.join(new_cache, "bootstrap")
    os.makedirs(boot, exist_ok=True)
    cfg_path = os.path.join(boot, "config.json")
    new_live = os.path.join(new_cache, "live")
    log("置き場: " + new_cache)

    # 旧 token / 旧置き場を温存 (新場所 → 旧 modules の順で探す)
    old_token = ""
    old_cache_raw = None
    for cand in (cfg_path, os.path.join(old_boot, "config.json")):
        if os.path.isfile(cand):
            try:
                oc = json.load(open(cand, encoding="utf-8"))
                old_token = oc.get("token", "") or old_token
                old_cache_raw = oc.get("cache_dir") or old_cache_raw
            except Exception:
                pass

    # bootstrap の中身を cache\bootstrap に、.mod を cache 直下に書き出す
    for name, b64 in _BOOT_FILES.items():
        _write_bytes(os.path.join(boot, name), base64.b64decode(b64))
    mod_text = ("// MayaTools 自動更新の受け取り役 (cache に集約)\n"
                "+ MayaToolsBootstrap 1.0 bootstrap\n"
                "PYTHONPATH +:= .\n")
    _write_bytes(os.path.join(new_cache, "MayaToolsBootstrap.mod"), mod_text.encode("utf-8"))
    log("bootstrap (更新役) を配置しました")

    # config.json (token 未指定なら旧 token 温存)。cache_dir は集約のため常に new_cache を記録。
    eff_token = token or old_token
    cfg = {
        "enabled": True,
        "source_mode": source_mode,
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "token": eff_token,
        "check_interval_hours": check_interval_hours,
        "cache_dir": new_cache,
    }
    with open(cfg_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    # updater を import (初回同期に使う)。起動時に古い updater が sys.modules に載っている
    # ことがあるので、今書き出したばかりの新しい方を確実に使うため一度捨てて読み直す。
    if boot not in sys.path:
        sys.path.insert(0, boot)
    sys.modules.pop("mayatools_updater", None)
    import mayatools_updater

    # Maya.env: MAYA_MODULE_PATH = [cache(bootstrap.mod用), cache/live(ツール本体)]。旧登録は除去。
    old_cache = _expand(old_cache_raw) if old_cache_raw else None
    remove_paths = [os.path.join(new_cache, "current")]
    if old_cache and _norm(old_cache) != _norm(new_cache):
        remove_paths += [old_cache, os.path.join(old_cache, "current"), os.path.join(old_cache, "live")]
    env_path = os.path.join(appdir, version, "Maya.env")
    env_status = _set_maya_env_cache(env_path, remove_paths, [new_cache, new_live])
    relocated = bool(old_cache) and _norm(old_cache) != _norm(new_cache)
    log("Maya.env を設定しました (" + env_status + ")")

    # 初回同期 (トークンがあれば): versions/<tag> を取得し live(junction) を張る
    synced = False
    if run_sync and eff_token:
        log("初回同期中… (ツール本体をダウンロード)")
        mayatools_updater.run(cfg_path, blocking=True)
        # DL したばかりの版を即 live に貼る (junction はロード中でも貼替可能)。
        # これで install 直後に live が最新を指す (反映は Maya 再起動後)。
        try:
            mayatools_updater.apply_pending(new_cache)
        except Exception:
            pass
        synced = mayatools_updater._is_valid_payload(new_live)

    # 掃除: 集約前の旧 bootstrap (~/maya/modules) と、レガシー current/pending
    import shutil
    shutil.rmtree(old_boot, ignore_errors=True)
    try:
        os.remove(os.path.join(old_modules, "MayaToolsBootstrap.mod"))
    except OSError:
        pass
    for legacy in ("current", "pending", "current_old"):
        try:
            shutil.rmtree(os.path.join(new_cache, legacy), ignore_errors=True)
        except Exception:
            pass

    if relocated:
        log("※ 旧置き場は不要です (削除可): " + old_cache)
    if not eff_token:
        log("※ token 未設定。token を入れて再実行すると初回同期されます。")
    elif synced:
        log("初回同期 OK (ツール本体を取得しました)")
    else:
        log("初回同期に失敗した可能性。" + os.path.join(new_cache, "update.log") + " を確認。")
    log("完了 → Maya を再起動してください。以後は起動のたび自動更新されます。")
    return {"ok": True, "cache": new_cache, "env_path": env_path,
            "relocated": relocated, "old_cache": old_cache,
            "synced": synced, "token_set": bool(eff_token)}


def _show_installer_ui(defaults):
    """PySide のインストーラ窓を出す。PySide が無い/GUI 無しなら例外を投げる (呼び側で headless へ)。"""
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
    except ImportError:
        from PySide2 import QtWidgets, QtCore, QtGui

    def _maya_main_window():
        try:
            import maya.OpenMayaUI as omui
            try:
                from shiboken6 import wrapInstance
            except ImportError:
                from shiboken2 import wrapInstance
            ptr = omui.MQtUtil.mainWindow()
            if ptr:
                return wrapInstance(int(ptr), QtWidgets.QWidget)
        except Exception:
            pass
        return None

    # --- 一貫した限定パレット (洗練の土台) ---
    BG, CARD, FIELD = "#1e2024", "#2a2d31", "#16171a"
    FG, MUTE, LINE = "#e8eaed", "#9aa0a6", "#3a3d42"
    ACCENT, ACCENT_H = "#4f8fd0", "#5fa0e0"
    OKC, ERRC = "#3fae6e", "#e0574d"

    CSS = (
        "QDialog{background:%(BG)s;}"
        "QLabel{color:%(FG)s;font-size:12px;}"
        "QLabel#title{color:#ffffff;font-size:16px;font-weight:600;}"
        "QLabel#sub{color:%(MUTE)s;font-size:11px;}"
        "QLabel#flabel{color:%(MUTE)s;font-size:11px;}"
        "#card{background:%(CARD)s;border:1px solid %(LINE)s;border-radius:8px;}"
        "QLineEdit,QComboBox{background:%(FIELD)s;color:%(FG)s;border:1px solid %(LINE)s;"
        "border-radius:6px;padding:7px 9px;font-size:12px;selection-background-color:%(ACCENT)s;}"
        "QLineEdit:focus,QComboBox:focus{border:1px solid %(ACCENT)s;}"
        "QComboBox::drop-down{border:0;width:18px;}"
        "QPlainTextEdit{background:%(FIELD)s;color:#aeb6c2;border:1px solid %(LINE)s;"
        "border-radius:6px;padding:6px;font-family:Consolas,'Courier New',monospace;font-size:11px;}"
        "QPushButton{background:transparent;color:%(MUTE)s;border:1px solid %(LINE)s;"
        "border-radius:6px;padding:8px 16px;font-size:12px;}"
        "QPushButton:hover{color:%(FG)s;border-color:#55585e;}"
        "QPushButton#primary{background:%(ACCENT)s;color:#ffffff;border:0;font-weight:600;padding:9px 20px;}"
        "QPushButton#primary:hover{background:%(ACCENT_H)s;}"
        "QPushButton#primary:disabled{background:#3a4047;color:#7d828a;}"
        "QToolButton{background:transparent;color:%(MUTE)s;border:0;font-size:11px;padding:2px;}"
        "QToolButton:hover{color:%(FG)s;}"
    ) % dict(BG=BG, CARD=CARD, FIELD=FIELD, FG=FG, MUTE=MUTE, LINE=LINE, ACCENT=ACCENT, ACCENT_H=ACCENT_H)

    dlg = QtWidgets.QDialog(_maya_main_window())
    dlg.setWindowTitle("MayaTools インストーラ")
    dlg.setStyleSheet(CSS)
    dlg.setMinimumWidth(470)
    root = QtWidgets.QVBoxLayout(dlg)
    root.setContentsMargins(22, 20, 22, 18)
    root.setSpacing(16)

    def _refit():
        # 展開/折りたたみ後にウィンドウを内容の高さへフィットし直す。
        # これが無いと「展開→折りたたみ」で余った高さが隙間として残る (縮まらない)。
        root.activate()
        dlg.resize(dlg.width(), dlg.sizeHint().height())

    # --- ヘッダー (明快な階層: 大きな見出し + 控えめな説明) ---
    head = QtWidgets.QVBoxLayout(); head.setSpacing(3)
    title = QtWidgets.QLabel("MayaTools をインストール"); title.setObjectName("title")
    sub = QtWidgets.QLabel("トークンと置き場を入れて [インストール]。完了したら Maya を再起動します。")
    sub.setObjectName("sub"); sub.setWordWrap(True)
    head.addWidget(title); head.addWidget(sub)
    root.addLayout(head)

    # --- 入力カード (関連項目をひとまとめ) ---
    card = QtWidgets.QFrame(); card.setObjectName("card")
    cl = QtWidgets.QVBoxLayout(card); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(12)

    def _label(text):
        lab = QtWidgets.QLabel(text); lab.setObjectName("flabel"); return lab

    # token (ラベルは上・フィールドは全幅)
    cl.addWidget(_label("GitHub Token"))
    ed_token = QtWidgets.QLineEdit(defaults.get("token", "") or "")
    ed_token.setEchoMode(QtWidgets.QLineEdit.Password)
    ed_token.setPlaceholderText("空のままなら既存のトークンを温存")
    btn_eye = QtWidgets.QToolButton(); btn_eye.setCheckable(True); btn_eye.setText("表示")
    btn_eye.setCursor(QtCore.Qt.PointingHandCursor)
    def _toggle_echo(on):
        ed_token.setEchoMode(QtWidgets.QLineEdit.Normal if on else QtWidgets.QLineEdit.Password)
        btn_eye.setText("隠す" if on else "表示")
    btn_eye.toggled.connect(_toggle_echo)
    trow = QtWidgets.QHBoxLayout(); trow.setSpacing(8)
    trow.addWidget(ed_token, 1); trow.addWidget(btn_eye)
    cl.addLayout(trow)

    # cache
    cl.addWidget(_label("置き場 (ツールの保存先)"))
    ed_cache = QtWidgets.QLineEdit(defaults.get("cache_dir", "") or "~/dev/MayaTools")
    ed_cache.setPlaceholderText("空=%LOCALAPPDATA%\\MayaTools")
    cl.addWidget(ed_cache)

    # 詳細 (累進的開示: 既定は畳んでおく)
    btn_adv = QtWidgets.QToolButton(); btn_adv.setCheckable(True); btn_adv.setText("▸ 詳細 (repo / mode)")
    btn_adv.setCursor(QtCore.Qt.PointingHandCursor)
    adv_box = QtWidgets.QWidget()
    af = QtWidgets.QFormLayout(adv_box); af.setContentsMargins(0, 6, 0, 0); af.setSpacing(8)
    af.setLabelAlignment(QtCore.Qt.AlignRight)
    ed_owner = QtWidgets.QLineEdit(defaults.get("owner", ""))
    ed_repo = QtWidgets.QLineEdit(defaults.get("repo", ""))
    cmb_mode = QtWidgets.QComboBox(); cmb_mode.addItems(["release", "zipball"])
    cmb_mode.setCurrentText(defaults.get("source_mode", "release"))
    ed_ref = QtWidgets.QLineEdit(defaults.get("ref", "main"))
    af.addRow("owner", ed_owner); af.addRow("repo", ed_repo)
    af.addRow("mode", cmb_mode); af.addRow("ref", ed_ref)
    adv_box.setVisible(False)
    def _toggle_adv(on):
        adv_box.setVisible(on); btn_adv.setText(("▾" if on else "▸") + " 詳細 (repo / mode)")
        _refit()
    btn_adv.toggled.connect(_toggle_adv)
    cl.addWidget(btn_adv, 0, QtCore.Qt.AlignLeft); cl.addWidget(adv_box)
    root.addWidget(card)

    # --- ステータスバナー (状態を色で即伝える。初期は非表示) ---
    status = QtWidgets.QLabel(""); status.setVisible(False); status.setWordWrap(True)
    root.addWidget(status)
    def _set_status(kind, text):
        col = {"run": ACCENT, "ok": OKC, "err": ERRC}.get(kind, ACCENT)
        bg = {"run": "#22303f", "ok": "#1f3a2c", "err": "#3a2624"}.get(kind, "#22303f")
        status.setStyleSheet("background:%s;border:1px solid %s;border-radius:6px;"
                             "color:#eef1f4;font-size:12px;padding:9px 12px;" % (bg, col))
        status.setText(text); status.setVisible(True)
        _refit()
        QtWidgets.QApplication.processEvents()

    # --- ログ (既定は畳む。必要な人だけ開く) ---
    btn_log = QtWidgets.QToolButton(); btn_log.setCheckable(True); btn_log.setText("▸ ログ")
    btn_log.setCursor(QtCore.Qt.PointingHandCursor)
    log_view = QtWidgets.QPlainTextEdit(); log_view.setReadOnly(True)
    log_view.setFixedHeight(120); log_view.setVisible(False)
    def _toggle_log(on):
        log_view.setVisible(on); btn_log.setText(("▾" if on else "▸") + " ログ")
        _refit()
    btn_log.toggled.connect(_toggle_log)
    root.addWidget(btn_log, 0, QtCore.Qt.AlignLeft); root.addWidget(log_view)

    # --- フッター (主要操作=アクセント色で1つだけ際立たせる) ---
    root.addStretch(1)   # 余白はここに集約 (上の隙間が散らばらない・縮小と併用)
    foot = QtWidgets.QHBoxLayout(); foot.addStretch(1)
    btn_close = QtWidgets.QPushButton("閉じる")
    btn_install = QtWidgets.QPushButton("インストール"); btn_install.setObjectName("primary")
    btn_install.setCursor(QtCore.Qt.PointingHandCursor)
    foot.addWidget(btn_close); foot.addWidget(btn_install)
    root.addLayout(foot)

    def _log(msg):
        log_view.appendPlainText(str(msg)); QtWidgets.QApplication.processEvents()

    def _on_install():
        btn_install.setEnabled(False); log_view.clear()
        if not btn_log.isChecked():
            btn_log.setChecked(True)
        _set_status("run", "インストール中…")
        _log("インストール開始…")
        try:
            res = _run_install(
                token=ed_token.text().strip(),
                owner=ed_owner.text().strip() or defaults.get("owner", ""),
                repo=ed_repo.text().strip() or defaults.get("repo", ""),
                source_mode=cmb_mode.currentText(),
                ref=ed_ref.text().strip() or defaults.get("ref", "main"),
                cache_dir=ed_cache.text().strip(),
                run_sync=defaults.get("run_sync", True),
                log=_log,
            )
            if res.get("synced"):
                _set_status("ok", "✓ 完了しました。Maya を再起動してください。")
            elif not res.get("token_set"):
                _set_status("run", "bootstrap は設置済。トークンを入れて再実行すると本体も取得します。")
            else:
                _set_status("ok", "設置は完了。本体取得は update.log を確認してください。")
        except Exception:
            import traceback
            _set_status("err", "✗ エラーが発生しました。ログを確認してください。")
            _log(traceback.format_exc())
        finally:
            btn_install.setEnabled(True)

    btn_install.clicked.connect(_on_install)
    btn_close.clicked.connect(dlg.close)
    dlg.show()
    dlg.raise_()
    return dlg


def main():
    defaults = dict(token=TOKEN, owner=OWNER, repo=REPO, source_mode=SOURCE_MODE,
                    ref=REF, cache_dir=CACHE_DIR, run_sync=RUN_INITIAL_SYNC)
    batch = False
    try:
        import maya.cmds as cmds
        batch = bool(cmds.about(batch=True))
    except Exception:
        pass
    if not batch:
        try:
            # 窓を保持しないと GC される。グローバルに退避。
            global _MT_INSTALLER_WIN
            _MT_INSTALLER_WIN = _show_installer_ui(defaults)
            return
        except Exception as e:
            print("[MayaTools] UI を表示できないので headless 実行します: %r" % (e,))
    _run_install(check_interval_hours=CHECK_INTERVAL_HOURS, log=print, **defaults)


main()
