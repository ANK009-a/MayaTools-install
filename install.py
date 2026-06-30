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
        'i+ODpeODvOani+evieOCiOOCiuWJjeOBqyBjdXJyZW50IOOBjOeiuuWumuOBmeOCiynjgIIKCj09'
        'IF9fZmlsZV9fIOOBq+S+neWtmOOBl+OBquOBhOOBk+OBqCAo6YeN6KaB44O75a6f5qmf44Gn6LiP'
        '44KT44Gg572gKSA9PQogIOS8muekvlBD44Gr44Gv54us6Ieq44Op44Oz44OB44OjICjkvos6IE1h'
        'eWFTaGVsZikg44GM5bGF44Gm44CB6LW35YuV5pmC44Gr5ZCEIHVzZXJTZXR1cC5weSDjgpIgKiro'
        'h6rliY3jgacKICBleGVjIOOBl+OBpuS9tei1sOWun+ihjCoq44GZ44KL44GT44Go44GM44GC44KL'
        '44CC44Gd44GuIGV4ZWMg5pa55byP44Gg44GoICoqX19maWxlX18g44GM5rih44KJ44Gq44GEL+WI'
        'peeJqSoq44Gr44Gq44KK44CBCiAgX19maWxlX18g44GL44KJIGNvbmZpZy5qc29uIOOBruWgtOaJ'
        'gOOCkuWHuuOBl+OBpuOBhOOCi+OBqCAqKnJ1bigpIOOCkuWRvOOBtuWJjeOBq+S+i+WklioqIOKG'
        'kiB1cGRhdGVyIOOBjAogIOi1t+WLleaZguOBq+S4gOW6puOCgui1sOOCieOBquOBhCAoPSDoh6rl'
        'i5Xmm7TmlrDjgoIgdG9rZW4g44Ky44O844OI44KC54Sh5Yq5KSDjgajjgYTjgYbkuovmlYXjgavj'
        'garjgosgKDIwMjYtMDYtMzAg56K65a6aKeOAggogIOKGkiBjb25maWcg44GvICoqbW9kdWxlIOiH'
        'qui6q+OBruWgtOaJgCAobWF5YXRvb2xzX3VwZGF0ZXIuX19maWxlX18pKiog44GL44KJ6Kej5rG6'
        '44GZ44KL44CCYm9vdHN0cmFwCiAgICDjg5Xjgqnjg6vjg4Djga8gLm1vZCDjga4gUFlUSE9OUEFU'
        'SCDjgavovInjgaPjgabjgYTjgovjga7jgacgYGltcG9ydCBtYXlhdG9vbHNfdXBkYXRlcmAg44Gv'
        'IF9fZmlsZV9fCiAgICDnhKHjgZfjgafjgoLpgJrjgovjgIJfX2ZpbGVfXyDjga8gKOS9v+OBiOOC'
        'jOOBsCkgc3lzLnBhdGgg6KOc5Yqp44GrIGJlc3QtZWZmb3J0IOOBp+S9v+OBhuOBoOOBkeOAggoi'
        'IiIKaW1wb3J0IG9zCmltcG9ydCBzeXMKaW1wb3J0IHRpbWUKaW1wb3J0IHRyYWNlYmFjawoKCmRl'
        'ZiBfcmVwb3J0X2Jvb3RfZmFpbHVyZSgpIC0+IE5vbmU6CiAgICAiIiLotbfli5XlpLHmlZfjgpIg'
        'Kirlv4XjgZrnl5Xot6HjgavmrovjgZkqKiAoTWF5YSDorablkYogKyDml6Llrprjgq3jg6Pjg4Pj'
        'grfjg6Xjga4gbG9nKeOAggoKICAgIOmBjuWOu+OAgeWkseaVl+OBjOeUu+mdouOBq+OCguODreOC'
        'sOOBq+OCguWHuuOBmuWOn+WboOeptuaYjuOBq+aZgumWk+OCkuimgeOBl+OBnyAoTWF5YVNoZWxm'
        'IOS9tei1sCBleGVjIOOBpwogICAgX19maWxlX18g5LiN5ZyoIOKGkiBjb25maWcg6Kej5rG65aSx'
        '5pWX44GM5o+h44KK44Gk44G244GV44KM44Gm44GE44GfKeOAguS6jOW6puOBqOeEoeiogOOBp+at'
        'u+OBquOBm+OBquOBhOOAggogICAgIiIiCiAgICB0YiA9IHRyYWNlYmFjay5mb3JtYXRfZXhjKCkK'
        'ICAgIHRyeToKICAgICAgICBmcm9tIG1heWEuYXBpLk9wZW5NYXlhIGltcG9ydCBNR2xvYmFsCiAg'
        'ICAgICAgTUdsb2JhbC5kaXNwbGF5V2FybmluZygiW01heWFUb29sc10g6Ieq5YuV5pu05paw44Gu'
        '6LW35YuV44Gr5aSx5pWXOlxuIiArIHRiKQogICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICBw'
        'YXNzCiAgICB0cnk6CiAgICAgICAgYmFzZSA9IG9zLmVudmlyb24uZ2V0KCJMT0NBTEFQUERBVEEi'
        'KSBvciBvcy5wYXRoLmpvaW4ob3MucGF0aC5leHBhbmR1c2VyKCJ+IiksICIubG9jYWwiLCAic2hh'
        'cmUiKQogICAgICAgIGQgPSBvcy5wYXRoLmpvaW4oYmFzZSwgIk1heWFUb29scyIpCiAgICAgICAg'
        'b3MubWFrZWRpcnMoZCwgZXhpc3Rfb2s9VHJ1ZSkKICAgICAgICB3aXRoIG9wZW4ob3MucGF0aC5q'
        'b2luKGQsICJ1cGRhdGUubG9nIiksICJhIiwgZW5jb2Rpbmc9InV0Zi04IikgYXMgZjoKICAgICAg'
        'ICAgICAgZi53cml0ZSh0aW1lLnN0cmZ0aW1lKCIlWS0lbS0lZCAlSDolTTolUyAiKQogICAgICAg'
        'ICAgICAgICAgICAgICsgIltNYXlhVG9vbHNdIHVzZXJTZXR1cCDotbfli5XlpLHmlZcgKF9fZmls'
        'ZV9fL2ltcG9ydCDop6PmsbopOlxuIiArIHRiICsgIlxuIikKICAgIGV4Y2VwdCBFeGNlcHRpb246'
        'CiAgICAgICAgcGFzcwoKCmRlZiBfYm9vdF9tYXlhdG9vbHNfdXBkYXRlcigpOgogICAgdHJ5Ogog'
        'ICAgICAgICMgX19maWxlX18g44GM5L2/44GI44KL6YCa5bi444GuIE1heWEg6LW35YuV44Gn44Gv'
        '6Ieq5YiG44Gu44OV44Kp44Or44OA44KSIHN5cy5wYXRoIOOBq+i2s+OBmeOAggogICAgICAgICMg'
        '44Gf44Gg44GXIE1heWFTaGVsZiDnrYnjgYwgZXhlYyDjgZnjgovnkrDlooPjgafjga8gX19maWxl'
        'X18g44GM54Sh44GEL+WIpeeJqeOBquOBruOBpyBiZXN0LWVmZm9ydOOAggogICAgICAgICMgKGJv'
        'b3RzdHJhcCDjg5Xjgqnjg6vjg4Djga8gLm1vZCDjga4gUFlUSE9OUEFUSCDjgafml6LjgavovInj'
        'gaPjgabjgYTjgovjgZ/jgoEgaW1wb3J0IOOBr+mAmuOCiykKICAgICAgICB0cnk6CiAgICAgICAg'
        'ICAgIGhlcmUwID0gb3MucGF0aC5kaXJuYW1lKG9zLnBhdGguYWJzcGF0aChfX2ZpbGVfXykpCiAg'
        'ICAgICAgICAgIGlmIGhlcmUwIGFuZCBoZXJlMCBub3QgaW4gc3lzLnBhdGg6CiAgICAgICAgICAg'
        'ICAgICBzeXMucGF0aC5pbnNlcnQoMCwgaGVyZTApCiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoK'
        'ICAgICAgICAgICAgcGFzcwoKICAgICAgICBpbXBvcnQgbWF5YXRvb2xzX3VwZGF0ZXIKCiAgICAg'
        'ICAgIyBjb25maWcg44GvICoq44Oi44K444Ol44O844Or6Ieq6Lqr44Gu5aC05omAKiog44GL44KJ'
        '6Kej5rG644GZ44KLIChfX2ZpbGVfXyDpnZ7kvp3lrZjjgafloIXniaIp44CCCiAgICAgICAgaGVy'
        'ZSA9IG9zLnBhdGguZGlybmFtZShvcy5wYXRoLmFic3BhdGgobWF5YXRvb2xzX3VwZGF0ZXIuX19m'
        'aWxlX18pKQogICAgICAgIG1heWF0b29sc191cGRhdGVyLnJ1bihvcy5wYXRoLmpvaW4oaGVyZSwg'
        'ImNvbmZpZy5qc29uIikpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIF9yZXBvcnRfYm9v'
        'dF9mYWlsdXJlKCkKCgojIOWkmumHjeWun+ihjOOCrOODvOODiTogTWF5YSDjga8gMSDjgrvjg4Pj'
        'grfjg6fjg7PkuK3jgasgdXNlclNldHVwLnB5IOOCkuikh+aVsOWbnua1geOBmeOBk+OBqOOBjOOB'
        'guOCi+OAggppZiBub3QgZ2V0YXR0cihzeXMsICJfbWF5YXRvb2xzX3VwZGF0ZXJfYm9vdGVkIiwg'
        'RmFsc2UpOgogICAgc3lzLl9tYXlhdG9vbHNfdXBkYXRlcl9ib290ZWQgPSBUcnVlCiAgICBfYm9v'
        'dF9tYXlhdG9vbHNfdXBkYXRlcigpCg=='
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
        '6KaBKeOAggojIHY2OiB1c2VyU2V0dXAg44KSIF9fZmlsZV9fIOmdnuS+neWtmOOBqyAoTWF5YVNo'
        'ZWxmIOetieOBruS9tei1sCBleGVjIOOBpyBydW4oKSDjgYzlkbzjgbDjgozjgarjgYTkuovmlYXj'
        'ga7kv67mraMp44CCCkJPT1RTVFJBUF9WRVJTSU9OID0gNgoKQUNDRVBUX0FTU0VUID0gImFwcGxp'
        'Y2F0aW9uL29jdGV0LXN0cmVhbSIKQUNDRVBUX0FSQ0hJVkUgPSAiKi8qIgoKX0xPR19DQUNIRSA9'
        'IE5vbmUgICMgcnVuKCkg44Gn56K65a6aCgoKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KIyDjg5Hjgrkg'
        'LyDjg63jgrAKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KZGVmIGRlZmF1bHRfY2FjaGVfZGlyKCkgLT4g'
        'c3RyOgogICAgYmFzZSA9IG9zLmVudmlyb24uZ2V0KCJMT0NBTEFQUERBVEEiKQogICAgaWYgbm90'
        'IGJhc2U6CiAgICAgICAgYmFzZSA9IG9zLnBhdGguam9pbihvcy5wYXRoLmV4cGFuZHVzZXIoIn4i'
        'KSwgIi5sb2NhbCIsICJzaGFyZSIpCiAgICByZXR1cm4gb3MucGF0aC5qb2luKGJhc2UsICJNYXlh'
        'VG9vbHMiKQoKCmRlZiBfbHAocGF0aDogc3RyKSAtPiBzdHI6CiAgICAiIiJXaW5kb3dzIE1BWF9Q'
        'QVRIKDI2MCkg5Zue6YG/44Gu6ZW344OR44K544OX44Os44OV44Kj44OD44Kv44K544CCIiIiCiAg'
        'ICBpZiBvcy5uYW1lICE9ICJudCI6CiAgICAgICAgcmV0dXJuIHBhdGgKICAgIHAgPSBvcy5wYXRo'
        'LmFic3BhdGgocGF0aCkKICAgIGlmIHAuc3RhcnRzd2l0aCgiXFxcXD9cXCIpOgogICAgICAgIHJl'
        'dHVybiBwCiAgICBpZiBwLnN0YXJ0c3dpdGgoIlxcXFwiKToKICAgICAgICByZXR1cm4gIlxcXFw/'
        'XFxVTkNcXCIgKyBwWzI6XQogICAgcmV0dXJuICJcXFxcP1xcIiArIHAKCgpkZWYgX2xvZyhtc2c6'
        'IHN0cikgLT4gTm9uZToKICAgIHRleHQgPSAiW01heWFUb29sc10gIiArIHN0cihtc2cpCiAgICBj'
        'YWNoZSA9IF9MT0dfQ0FDSEUgb3IgZGVmYXVsdF9jYWNoZV9kaXIoKQogICAgdHJ5OgogICAgICAg'
        'IG9zLm1ha2VkaXJzKGNhY2hlLCBleGlzdF9vaz1UcnVlKQogICAgICAgIHdpdGggb3Blbihvcy5w'
        'YXRoLmpvaW4oY2FjaGUsICJ1cGRhdGUubG9nIiksICJhIiwgZW5jb2Rpbmc9InV0Zi04IikgYXMg'
        'ZjoKICAgICAgICAgICAgZi53cml0ZSh0aW1lLnN0cmZ0aW1lKCIlWS0lbS0lZCAlSDolTTolUyAi'
        'KSArIHRleHQgKyAiXG4iKQogICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICBwYXNzCiAgICB0'
        'cnk6CiAgICAgICAgaWYgdGhyZWFkaW5nLmN1cnJlbnRfdGhyZWFkKCkgaXMgdGhyZWFkaW5nLm1h'
        'aW5fdGhyZWFkKCk6CiAgICAgICAgICAgIGZyb20gbWF5YS5hcGkuT3Blbk1heWEgaW1wb3J0IE1H'
        'bG9iYWwgICMgbm9xYTogUExDMDQxNQogICAgICAgICAgICBNR2xvYmFsLmRpc3BsYXlJbmZvKHRl'
        'eHQpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHBhc3MKCgojIC0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLQojIOioreWumgojIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLQpkZWYgbG9hZF9jb25maWcocGF0aDog'
        'c3RyIHwgTm9uZSA9IE5vbmUpIC0+IGRpY3Q6CiAgICBpZiBwYXRoIGlzIE5vbmU6CiAgICAgICAg'
        'cGF0aCA9IG9zLnBhdGguam9pbihvcy5wYXRoLmRpcm5hbWUob3MucGF0aC5hYnNwYXRoKF9fZmls'
        'ZV9fKSksICJjb25maWcuanNvbiIpCiAgICB3aXRoIG9wZW4ocGF0aCwgInIiLCBlbmNvZGluZz0i'
        'dXRmLTgiKSBhcyBmOgogICAgICAgIHJldHVybiBqc29uLmxvYWQoZikKCgojIC0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLQojIEhUVFAgKHByaXZhdGUgcmVwbzog44Ob44K544OI44GM5aSJ44KP44KLIHJlZGly'
        'ZWN0IOOBp+OBryBBdXRob3JpemF0aW9uIOOCkuiQveOBqOOBmSkKIyAtLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0KY2xhc3MgX0F1dGhBd2FyZVJlZGlyZWN0KHVybGxpYi5yZXF1ZXN0LkhUVFBSZWRpcmVjdEhh'
        'bmRsZXIpOgogICAgZGVmIHJlZGlyZWN0X3JlcXVlc3Qoc2VsZiwgcmVxLCBmcCwgY29kZSwgbXNn'
        'LCBoZWFkZXJzLCBuZXd1cmwpOgogICAgICAgIG5ldyA9IHN1cGVyKCkucmVkaXJlY3RfcmVxdWVz'
        'dChyZXEsIGZwLCBjb2RlLCBtc2csIGhlYWRlcnMsIG5ld3VybCkKICAgICAgICBpZiBuZXcgaXMg'
        'bm90IE5vbmU6CiAgICAgICAgICAgIHRyeToKICAgICAgICAgICAgICAgIGlmIHVybGxpYi5wYXJz'
        'ZS51cmxzcGxpdChyZXEuZnVsbF91cmwpLmhvc3RuYW1lICE9IHVybGxpYi5wYXJzZS51cmxzcGxp'
        'dChuZXd1cmwpLmhvc3RuYW1lOgogICAgICAgICAgICAgICAgICAgIGZvciBrIGluIGxpc3QobmV3'
        'LmhlYWRlcnMua2V5cygpKToKICAgICAgICAgICAgICAgICAgICAgICAgaWYgay5sb3dlcigpID09'
        'ICJhdXRob3JpemF0aW9uIjoKICAgICAgICAgICAgICAgICAgICAgICAgICAgIGRlbCBuZXcuaGVh'
        'ZGVyc1trXQogICAgICAgICAgICAgICAgICAgIG5ldy51bnJlZGlyZWN0ZWRfaGRycy5wb3AoIkF1'
        'dGhvcml6YXRpb24iLCBOb25lKQogICAgICAgICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAg'
        'ICAgICAgICAgcGFzcwogICAgICAgIHJldHVybiBuZXcKCgpkZWYgX29wZW5lcigpOgogICAgcmV0'
        'dXJuIHVybGxpYi5yZXF1ZXN0LmJ1aWxkX29wZW5lcihfQXV0aEF3YXJlUmVkaXJlY3QoKSkKCgpk'
        'ZWYgX3JlcXVlc3QodXJsOiBzdHIsIHRva2VuOiBzdHIsIGFjY2VwdDogc3RyKSAtPiB1cmxsaWIu'
        'cmVxdWVzdC5SZXF1ZXN0OgogICAgcmVxID0gdXJsbGliLnJlcXVlc3QuUmVxdWVzdCh1cmwpCiAg'
        'ICByZXEuYWRkX2hlYWRlcigiVXNlci1BZ2VudCIsIFVTRVJfQUdFTlQpCiAgICByZXEuYWRkX2hl'
        'YWRlcigiQWNjZXB0IiwgYWNjZXB0KQogICAgaWYgdG9rZW46CiAgICAgICAgcmVxLmFkZF9oZWFk'
        'ZXIoIkF1dGhvcml6YXRpb24iLCAiQmVhcmVyICIgKyB0b2tlbikKICAgIHJldHVybiByZXEKCgpk'
        'ZWYgX2FwaV9qc29uKHVybDogc3RyLCB0b2tlbjogc3RyKSAtPiBkaWN0OgogICAgcmVxID0gX3Jl'
        'cXVlc3QodXJsLCB0b2tlbiwgImFwcGxpY2F0aW9uL3ZuZC5naXRodWIranNvbiIpCiAgICB3aXRo'
        'IF9vcGVuZXIoKS5vcGVuKHJlcSwgdGltZW91dD1BUElfVElNRU9VVCkgYXMgcjoKICAgICAgICBy'
        'ZXR1cm4ganNvbi5sb2FkcyhyLnJlYWQoKS5kZWNvZGUoInV0Zi04IikpCgoKZGVmIF9kb3dubG9h'
        'ZCh1cmw6IHN0ciwgZGVzdDogc3RyLCB0b2tlbjogc3RyLCBhY2NlcHQ6IHN0cikgLT4gTm9uZToK'
        'ICAgICMgYWNjZXB0IOOBr+WPluW+l+eoruWIpeOBp+WkieOBiOOCizogYXNzZXQ9b2N0ZXQtc3Ry'
        'ZWFtIC8gemlwYmFsbD0qLyogKG9jdGV0IOOBoOOBqCA0MTUp44CCCiAgICByZXEgPSBfcmVxdWVz'
        'dCh1cmwsIHRva2VuLCBhY2NlcHQpCiAgICB3aXRoIF9vcGVuZXIoKS5vcGVuKHJlcSwgdGltZW91'
        'dD1ET1dOTE9BRF9USU1FT1VUKSBhcyByLCBvcGVuKGRlc3QsICJ3YiIpIGFzIGY6CiAgICAgICAg'
        'c2h1dGlsLmNvcHlmaWxlb2JqKHIsIGYsIGxlbmd0aD0yNTYgKiAxMDI0KQoKCmRlZiBfaHR0cF9o'
        'aW50KGNvZGU6IGludCkgLT4gc3RyOgogICAgaWYgY29kZSA9PSA0MDE6CiAgICAgICAgcmV0dXJu'
        'ICLjg4jjg7zjgq/jg7PjgYznhKHlirkv5pyf6ZmQ5YiH44KM44Gu5Y+v6IO95oCnIChjb25maWcu'
        'anNvbiDjga4gdG9rZW4g44KS56K66KqNKSIKICAgIGlmIGNvZGUgPT0gNDAzOgogICAgICAgIHJl'
        'dHVybiAoIuaoqemZkOS4jei2syBvciDjg6zjg7zjg4jliLbpmZDjgIJmaW5lLWdyYWluZWQgUEFU'
        'IOOBriBSZXBvc2l0b3J5IGFjY2VzcyDjgavlr77osaEgcmVwbyDjgpLlkKvjgoHjgIEiCiAgICAg'
        'ICAgICAgICAgICAiQ29udGVudHM9UmVhZCDjgpLku5jkuI7jgZfjgabjgYTjgovjgYvnorroqo0g'
        'KGNsYXNzaWMgdG9rZW4g44Gq44KJIHJlcG8g44K544Kz44O844OXKSIpCiAgICBpZiBjb2RlID09'
        'IDQwNDoKICAgICAgICByZXR1cm4gIm93bmVyL3JlcG8vcmVmL3NvdXJjZV9tb2RlIOOCkueiuuiq'
        'jSAocHJpdmF0ZSDjgacgdG9rZW4g44GM44Gd44GuIHJlcG8g44KS6KaL44KJ44KM44Gq44GE5aC0'
        '5ZCI44KCIDQwNCkiCiAgICByZXR1cm4gInRva2VuL293bmVyL3JlcG8vc291cmNlX21vZGUg44KS'
        '56K66KqNIgoKCmRlZiBfcmVzb2x2ZV9yZW1vdGUoY2ZnOiBkaWN0KSAtPiBkaWN0OgogICAgIiIi'
        'eyJ2ZXJzaW9uIiwgInVybCIsICJhY2NlcHQifSDjgpLov5TjgZnjgILlpLHmlZfmmYLjga/kvovl'
        'pJbjgIIiIiIKICAgIG93bmVyLCByZXBvLCB0b2tlbiA9IGNmZ1sib3duZXIiXSwgY2ZnWyJyZXBv'
        'Il0sIGNmZy5nZXQoInRva2VuIiwgIiIpCiAgICBtb2RlID0gY2ZnLmdldCgic291cmNlX21vZGUi'
        'LCAicmVsZWFzZSIpCiAgICBpZiBtb2RlID09ICJyZWxlYXNlIjoKICAgICAgICBkYXRhID0gX2Fw'
        'aV9qc29uKGYie0FQSV9ST09UfS9yZXBvcy97b3duZXJ9L3tyZXBvfS9yZWxlYXNlcy9sYXRlc3Qi'
        'LCB0b2tlbikKICAgICAgICB2ZXJzaW9uID0gZGF0YS5nZXQoInRhZ19uYW1lIikgb3IgZGF0YS5n'
        'ZXQoIm5hbWUiKSBvciAiIgogICAgICAgIGZvciBhIGluIGRhdGEuZ2V0KCJhc3NldHMiLCBbXSk6'
        'CiAgICAgICAgICAgIGlmIHN0cihhLmdldCgibmFtZSIsICIiKSkubG93ZXIoKS5lbmRzd2l0aCgi'
        'LnppcCIpOgogICAgICAgICAgICAgICAgcmV0dXJuIHsidmVyc2lvbiI6IHZlcnNpb24sICJ1cmwi'
        'OiBhWyJ1cmwiXSwgImFjY2VwdCI6IEFDQ0VQVF9BU1NFVH0KICAgICAgICByZXR1cm4geyJ2ZXJz'
        'aW9uIjogdmVyc2lvbiwgInVybCI6IGRhdGFbInppcGJhbGxfdXJsIl0sICJhY2NlcHQiOiBBQ0NF'
        'UFRfQVJDSElWRX0KICAgIHJlZiA9IGNmZy5nZXQoInJlZiIsICJtYWluIikKICAgIGRhdGEgPSBf'
        'YXBpX2pzb24oZiJ7QVBJX1JPT1R9L3JlcG9zL3tvd25lcn0ve3JlcG99L2NvbW1pdHMve3JlZn0i'
        'LCB0b2tlbikKICAgIHJldHVybiB7InZlcnNpb24iOiBkYXRhWyJzaGEiXSwKICAgICAgICAgICAg'
        'InVybCI6IGYie0FQSV9ST09UfS9yZXBvcy97b3duZXJ9L3tyZXBvfS96aXBiYWxsL3tyZWZ9IiwK'
        'ICAgICAgICAgICAgImFjY2VwdCI6IEFDQ0VQVF9BUkNISVZFfQoKCiMgLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tCiMg44Kt44Oj44OD44K344OlIC8g54mIIC8ganVuY3Rpb24KIyAtLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0KZGVmIF9zYWZlX3RhZyh0YWc6IHN0cikgLT4gc3RyOgogICAgcmV0dXJuICIiLmpvaW4oYyBp'
        'ZiAoYy5pc2FsbnVtKCkgb3IgYyBpbiAiLl8tIikgZWxzZSAiXyIgZm9yIGMgaW4gc3RyKHRhZykp'
        'CgoKZGVmIF92ZXJzaW9uc19kaXIoY2FjaGU6IHN0cikgLT4gc3RyOgogICAgcmV0dXJuIG9zLnBh'
        'dGguam9pbihjYWNoZSwgInZlcnNpb25zIikKCgpkZWYgX3ZlcnNpb25fcGF0aChjYWNoZTogc3Ry'
        'LCB0YWc6IHN0cikgLT4gc3RyOgogICAgcmV0dXJuIG9zLnBhdGguam9pbihfdmVyc2lvbnNfZGly'
        'KGNhY2hlKSwgX3NhZmVfdGFnKHRhZykpCgoKZGVmIF9saXZlX3BhdGgoY2FjaGU6IHN0cikgLT4g'
        'c3RyOgogICAgcmV0dXJuIG9zLnBhdGguam9pbihjYWNoZSwgTElWRSkKCgpkZWYgX2lzX3ZhbGlk'
        'X3BheWxvYWQocm9vdDogc3RyKSAtPiBib29sOgogICAgcmV0dXJuIG9zLnBhdGguaXNmaWxlKG9z'
        'LnBhdGguam9pbihyb290LCBTRU5USU5FTCkpCgoKZGVmIF9pc19saW5rKHBhdGg6IHN0cikgLT4g'
        'Ym9vbDoKICAgICIiInBhdGgg44GMIGp1bmN0aW9uL3N5bWxpbmsgKHJlcGFyc2UgcG9pbnQpIOOB'
        'i+OAgiIiIgogICAgdHJ5OgogICAgICAgIGlmIG9zLnBhdGguaXNsaW5rKHBhdGgpOgogICAgICAg'
        'ICAgICByZXR1cm4gVHJ1ZQogICAgICAgIHJldHVybiBvcy5wYXRoLmlzZGlyKHBhdGgpIGFuZCBi'
        'b29sKGdldGF0dHIob3MubHN0YXQocGF0aCksICJzdF9yZXBhcnNlX3RhZyIsIDApKQogICAgZXhj'
        'ZXB0IE9TRXJyb3I6CiAgICAgICAgcmV0dXJuIEZhbHNlCgoKZGVmIF9yZW1vdmVfbGluayhwYXRo'
        'OiBzdHIpIC0+IE5vbmU6CiAgICAiIiJqdW5jdGlvbi9zeW1saW5rIOOCkuOAgeOCv+ODvOOCsuOD'
        'g+ODiOOBq+inpuOCjOOBmuOBq+WkluOBmeOAgiIiIgogICAgaWYgbm90IG9zLnBhdGgubGV4aXN0'
        'cyhwYXRoKToKICAgICAgICByZXR1cm4KICAgIHRyeToKICAgICAgICBvcy5ybWRpcihwYXRoKSAg'
        'ICAgICAgIyBqdW5jdGlvbiDjga/jgZPjgozjgaflpJbjgozjgosgKOOCv+ODvOOCsuODg+ODiOOB'
        'ruS4rei6q+OBr+a2iOOBiOOBquOBhCkKICAgIGV4Y2VwdCBPU0Vycm9yOgogICAgICAgIHRyeToK'
        'ICAgICAgICAgICAgb3MudW5saW5rKHBhdGgpCiAgICAgICAgZXhjZXB0IE9TRXJyb3I6CiAgICAg'
        'ICAgICAgIHBhc3MKCgpkZWYgX21ha2VfanVuY3Rpb24obGluazogc3RyLCB0YXJnZXQ6IHN0cikg'
        'LT4gTm9uZToKICAgICIiImxpbmsg44KSIGp1bmN0aW9uIOOBqOOBl+OBpiB0YXJnZXQg44Gr5ZCR'
        '44GR44KLICjml6LlrZggbGluayDjga/lpJbjgZkp44CCbG9ja2VkIOOBp+OCguaIkOWKn+OAgiIi'
        'IgogICAgaWYgb3MubmFtZSA9PSAibnQiOgogICAgICAgICMgY21kIOOBriBta2xpbmsg44GvIGJh'
        'Y2tzbGFzaCDlv4XpoIjjgIIiQzovVXNlcnMvLi4uIiDjgaDjgaggL1VzZXJzIOOCkuOCueOCpOOD'
        'g+ODgeOBqOiqpOiqjeOBmeOCi+OAggogICAgICAgIGxpbmsgPSBvcy5wYXRoLm5vcm1wYXRoKGxp'
        'bmspCiAgICAgICAgdGFyZ2V0ID0gb3MucGF0aC5ub3JtcGF0aCh0YXJnZXQpCiAgICBfcmVtb3Zl'
        'X2xpbmsobGluaykKICAgIGlmIG9zLm5hbWUgPT0gIm50IjoKICAgICAgICAjIGJ5dGVzIOOBp+WP'
        'luW+lyAoY21kIOOBryBDUDkzMiDlh7rlipvjgarjga7jgacgdGV4dD1UcnVlIOOBoOOBqCByZWFk'
        'ZXIgdGhyZWFkIOOBjCBkZWNvZGUg5L6L5aSWKQogICAgICAgIHIgPSBzdWJwcm9jZXNzLnJ1bihb'
        'ImNtZCIsICIvYyIsICJta2xpbmsiLCAiL0oiLCBsaW5rLCB0YXJnZXRdLCBjYXB0dXJlX291dHB1'
        'dD1UcnVlKQogICAgICAgIGlmIHIucmV0dXJuY29kZSAhPSAwIG9yIG5vdCBvcy5wYXRoLmlzZGly'
        'KGxpbmspOgogICAgICAgICAgICBtc2cgPSAoci5zdGRlcnIgb3Igci5zdGRvdXQgb3IgYiIiKS5k'
        'ZWNvZGUoImNwOTMyIiwgInJlcGxhY2UiKS5zdHJpcCgpCiAgICAgICAgICAgIHJhaXNlIE9TRXJy'
        'b3IoImp1bmN0aW9uIOS9nOaIkOWkseaVlzogJXMgLT4gJXMgOiAlcyIgJSAobGluaywgdGFyZ2V0'
        'LCBtc2cpKQogICAgZWxzZToKICAgICAgICBvcy5zeW1saW5rKHRhcmdldCwgbGluaywgdGFyZ2V0'
        'X2lzX2RpcmVjdG9yeT1UcnVlKQoKCmRlZiBfcmVhZF9zdGF0ZShjYWNoZTogc3RyKSAtPiBkaWN0'
        'OgogICAgdHJ5OgogICAgICAgIHdpdGggb3Blbihvcy5wYXRoLmpvaW4oY2FjaGUsICJzdGF0ZS5q'
        'c29uIiksICJyIiwgZW5jb2Rpbmc9InV0Zi04IikgYXMgZjoKICAgICAgICAgICAgcmV0dXJuIGpz'
        'b24ubG9hZChmKQogICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICByZXR1cm4ge30KCgpkZWYg'
        'X3dyaXRlX3N0YXRlKGNhY2hlOiBzdHIsIHN0YXRlOiBkaWN0KSAtPiBOb25lOgogICAgdHJ5Ogog'
        'ICAgICAgIHdpdGggb3Blbihvcy5wYXRoLmpvaW4oY2FjaGUsICJzdGF0ZS5qc29uIiksICJ3Iiwg'
        'ZW5jb2Rpbmc9InV0Zi04IikgYXMgZjoKICAgICAgICAgICAganNvbi5kdW1wKHN0YXRlLCBmLCBl'
        'bnN1cmVfYXNjaWk9RmFsc2UsIGluZGVudD0yKQogICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAg'
        'ICBfbG9nKCJzdGF0ZS5qc29uIOabuOi+vOWkseaVlzpcbiIgKyB0cmFjZWJhY2suZm9ybWF0X2V4'
        'YygpKQoKCmRlZiBfZmxhdHRlbl9zaW5nbGVfdG9wKGV4dHJhY3RfZGlyOiBzdHIpIC0+IHN0cjoK'
        'ICAgIGVudHJpZXMgPSBvcy5saXN0ZGlyKGV4dHJhY3RfZGlyKQogICAgaWYgbGVuKGVudHJpZXMp'
        'ID09IDE6CiAgICAgICAgaW5uZXIgPSBvcy5wYXRoLmpvaW4oZXh0cmFjdF9kaXIsIGVudHJpZXNb'
        'MF0pCiAgICAgICAgaWYgb3MucGF0aC5pc2Rpcihpbm5lcik6CiAgICAgICAgICAgIHJldHVybiBp'
        'bm5lcgogICAgcmV0dXJuIGV4dHJhY3RfZGlyCgoKZGVmIF9jbGVhbnVwX3ZlcnNpb25zKGNhY2hl'
        'OiBzdHIsIGFsd2F5c19rZWVwKSAtPiBOb25lOgogICAgIiIi54mI44OV44Kp44Or44OA44KS5Y+k'
        '44GE44KC44Gu44GL44KJ5o6D6ZmkIChLRUVQX1JFQ0VOVCDku7YgKyBhbHdheXNfa2VlcCDjga/m'
        'rovjgZkp44CCbG9ja2VkIOOBr+eEoeimluOAgiIiIgogICAgdmQgPSBfdmVyc2lvbnNfZGlyKGNh'
        'Y2hlKQogICAgaWYgbm90IG9zLnBhdGguaXNkaXIodmQpOgogICAgICAgIHJldHVybgogICAga2Vl'
        'cCA9IHtfc2FmZV90YWcodCkgZm9yIHQgaW4gYWx3YXlzX2tlZXAgaWYgdH0KICAgIGRpcnMgPSBz'
        'b3J0ZWQoZCBmb3IgZCBpbiBvcy5saXN0ZGlyKHZkKSBpZiBvcy5wYXRoLmlzZGlyKG9zLnBhdGgu'
        'am9pbih2ZCwgZCkpKQogICAgIyB0YWcg44GvIGRpc3QtWVlZWU1NREQtSEhNTVNTIOOBp+aYh+mg'
        'hj3mmYLns7vliJfjgILmlrDjgZfjgYQgS0VFUF9SRUNFTlQg5Lu244Gv5q6L44GZ44CCCiAgICBm'
        'b3IgZCBpbiBkaXJzWzotS0VFUF9SRUNFTlRdIGlmIGxlbihkaXJzKSA+IEtFRVBfUkVDRU5UIGVs'
        'c2UgW106CiAgICAgICAgaWYgZCBpbiBrZWVwOgogICAgICAgICAgICBjb250aW51ZQogICAgICAg'
        'IHNodXRpbC5ybXRyZWUoX2xwKG9zLnBhdGguam9pbih2ZCwgZCkpLCBpZ25vcmVfZXJyb3JzPVRy'
        'dWUpCgoKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KIyDpgannlKggKGxpdmUganVuY3Rpb24g44Gu6LK8'
        '5pu/KSDigJQgbG9ja2VkIOOBp+OCguaIkOWKnwojIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLQpkZWYgYXBw'
        'bHlfcGVuZGluZyhjYWNoZTogc3RyKSAtPiBib29sOgogICAgIiIic3RhdGUucGVuZGluZyDjgYzj'
        'gYLjgozjgbAgbGl2ZSDjgpIgdmVyc2lvbnMvPHBlbmRpbmc+IOOBuOiyvOOCiuabv+OBiOOCi+OA'
        'giIiIgogICAgc3RhdGUgPSBfcmVhZF9zdGF0ZShjYWNoZSkKICAgIHBlbmRpbmcgPSBzdGF0ZS5n'
        'ZXQoInBlbmRpbmciKQogICAgaWYgbm90IHBlbmRpbmc6CiAgICAgICAgcmV0dXJuIEZhbHNlCiAg'
        'ICB2cCA9IF92ZXJzaW9uX3BhdGgoY2FjaGUsIHBlbmRpbmcpCiAgICBpZiBub3QgX2lzX3ZhbGlk'
        'X3BheWxvYWQodnApOgogICAgICAgIHN0YXRlWyJwZW5kaW5nIl0gPSBOb25lCiAgICAgICAgX3dy'
        'aXRlX3N0YXRlKGNhY2hlLCBzdGF0ZSkKICAgICAgICByZXR1cm4gRmFsc2UKICAgIHRyeToKICAg'
        'ICAgICBfbWFrZV9qdW5jdGlvbihfbGl2ZV9wYXRoKGNhY2hlKSwgdnApCiAgICBleGNlcHQgT1NF'
        'cnJvciBhcyBlOgogICAgICAgIF9sb2coImxpdmUg5YiH5pu/44Gr5aSx5pWXICjmrKHlm57lho3o'
        'qabooYwpOiAlcyIgJSBlKQogICAgICAgIHJldHVybiBGYWxzZQogICAgc3RhdGVbImFjdGl2ZSJd'
        'ID0gcGVuZGluZwogICAgc3RhdGVbInBlbmRpbmciXSA9IE5vbmUKICAgIF93cml0ZV9zdGF0ZShj'
        'YWNoZSwgc3RhdGUpCiAgICBfbG9nKCLmm7TmlrDjgpLpgannlKjjgZfjgb7jgZfjgZ8gKGxpdmUg'
        'LT4gJXMpIiAlIHN0cihwZW5kaW5nKVs6MTZdKQogICAgcmV0dXJuIFRydWUKCgpkZWYgX3NldF90'
        'b29sc19lbmFibGVkKGNhY2hlOiBzdHIsIGVuYWJsZWQ6IGJvb2wpIC0+IE5vbmU6CiAgICAiIiJ0'
        'b2tlbiDjga7mnInnhKHjgavlv5zjgZjjgabjg4Tjg7zjg6sgKGxpdmUganVuY3Rpb24pIOOCkuac'
        'ieWKuS/nhKHlirnljJbjgZnjgovjgIIKCiAgICB0b2tlbiDoqo3oqLzjgYznhKHjgYTjgajjgY3j'
        'ga/jg4Tjg7zjg6vjgpLoqq3jgb/ovrzjgb7jgZvjgarjgYTmlrnph53jgIJNYXlhIOOBryA8Y2Fj'
        'aGU+L2xpdmUg44KSCiAgICBNQVlBX01PRFVMRV9QQVRIIOe1jOeUseOBp+ODreODvOODieOBmeOC'
        'i+OBruOBp+OAgSoqbGl2ZSDjgpLlpJbjgZvjgbAgTWF5YSDjga/jg4Tjg7zjg6vjgpLopovjgaTj'
        'gZHjgonjgozjgarjgYQqKgogICAgKOWPjeaYoOOBr+asoeWbnui1t+WLlSnjgILmnInlirnljJbj'
        'ga8gbGl2ZSDjgYznhKHjgY8gYWN0aXZlIOeJiOOBjOOBguOCjOOBsOiyvOOCiuebtOOBmSAo54Sh'
        '5Yq554q25oWL44GL44KJ44Gu5b6p5biw44O744ON44OD44OI5LiN6KaBKeOAggogICAgIiIiCiAg'
        'ICBsaXZlID0gX2xpdmVfcGF0aChjYWNoZSkKICAgIGlmIG5vdCBlbmFibGVkOgogICAgICAgIGlm'
        'IF9pc19saW5rKGxpdmUpOgogICAgICAgICAgICBfcmVtb3ZlX2xpbmsobGl2ZSkKICAgICAgICBy'
        'ZXR1cm4KICAgIGlmIF9pc19saW5rKGxpdmUpIGFuZCBfaXNfdmFsaWRfcGF5bG9hZChsaXZlKToK'
        'ICAgICAgICByZXR1cm4gICMg5pei44Gr5pyJ5Yq5CiAgICBhY3RpdmUgPSBfcmVhZF9zdGF0ZShj'
        'YWNoZSkuZ2V0KCJhY3RpdmUiKQogICAgaWYgYWN0aXZlOgogICAgICAgIHZwID0gX3ZlcnNpb25f'
        'cGF0aChjYWNoZSwgYWN0aXZlKQogICAgICAgIGlmIF9pc192YWxpZF9wYXlsb2FkKHZwKToKICAg'
        'ICAgICAgICAgdHJ5OgogICAgICAgICAgICAgICAgX21ha2VfanVuY3Rpb24obGl2ZSwgdnApCiAg'
        'ICAgICAgICAgICAgICBfbG9nKCLjg4Tjg7zjg6vjgpLmnInlirnljJbjgZfjgb7jgZfjgZ8gKGxp'
        'dmUgLT4gJXMpIiAlIHN0cihhY3RpdmUpWzoxNl0pCiAgICAgICAgICAgIGV4Y2VwdCBPU0Vycm9y'
        'IGFzIGU6CiAgICAgICAgICAgICAgICBfbG9nKCLjg4Tjg7zjg6vmnInlirnljJbjgavlpLHmlZcg'
        'KOasoeWbnuWGjeippuihjCk6ICVzIiAlIGUpCgoKZGVmIF9tYXJrX2F1dGgoY2FjaGU6IHN0ciwg'
        'dmFsdWU6IHN0cikgLT4gTm9uZToKICAgICIiIuebtOi/keOBruiqjeiovOe1kOaenOOCkiBzdGF0'
        'ZVsnYXV0aCddIOOBq+S/neWtmCAoJ29rJy8nZmFpbCcp44CCcnVuIOWGkumgreOBp+WQjOacn+ea'
        'hOOBq+WPgueFp+OBl+OBpgogICAgJ2ZhaWwnIOOBquOCiSBsaXZlIOOCkuWkluOBl+OBn+OBvuOB'
        'viBhcHBseSDjgoLjgZfjgarjgYQgKD0g54Sh5Yq5IHRva2VuIOOBpyBsaXZlIOOBjOWGjeeUn+aI'
        'kOOBleOCjOOCi+OBruOCkumYsuOBkCnjgIIiIiIKICAgIHRyeToKICAgICAgICBzdCA9IF9yZWFk'
        'X3N0YXRlKGNhY2hlKQogICAgICAgIHN0WyJhdXRoIl0gPSB2YWx1ZQogICAgICAgIF93cml0ZV9z'
        'dGF0ZShjYWNoZSwgc3QpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHBhc3MKCgojIC0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLQojIGJvb3RzdHJhcCAodXBkYXRlciDoh6rouqspIOOBruiHquW3seab'
        'tOaWsCDigJQgaW5zdGFsbC5weSDjgpLlho3phY3luIPjgZvjgZrjgasgdXBkYXRlciDjgpLmm7Tm'
        'lrDjgZnjgosKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KZGVmIF9wYXJzZV9ib290c3RyYXBfdmVyc2lv'
        'bihweV9wYXRoOiBzdHIpOgogICAgIiIi44OV44Kh44Kk44Or44GL44KJIEJPT1RTVFJBUF9WRVJT'
        'SU9OIOOBruWApOOCkuODhuOCreOCueODiOino+aekOOBp+iqreOCgCAoaW1wb3J0IOOBr+OBl+OB'
        'quOBhCnjgIIiIiIKICAgIGltcG9ydCByZQogICAgdHJ5OgogICAgICAgIHdpdGggb3BlbihweV9w'
        'YXRoLCAiciIsIGVuY29kaW5nPSJ1dGYtOCIsIGVycm9ycz0iaWdub3JlIikgYXMgZjoKICAgICAg'
        'ICAgICAgZm9yIGxpbmUgaW4gZjoKICAgICAgICAgICAgICAgIG0gPSByZS5tYXRjaChyIlxzKkJP'
        'T1RTVFJBUF9WRVJTSU9OXHMqPVxzKihcZCspIiwgbGluZSkKICAgICAgICAgICAgICAgIGlmIG06'
        'CiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIGludChtLmdyb3VwKDEpKQogICAgZXhjZXB0IEV4'
        'Y2VwdGlvbjoKICAgICAgICBwYXNzCiAgICByZXR1cm4gTm9uZQoKCmRlZiBfcmVmcmVzaF9ib290'
        'c3RyYXAoY2FjaGU6IHN0cikgLT4gTm9uZToKICAgICIiImxpdmUgKOmBqeeUqOa4iOOBrueJiCkg'
        '44Gr5ZCM5qKx44GV44KM44Gf5paw44GX44GEIGJvb3RzdHJhcCDjgYzjgYLjgozjgbAgdXBkYXRl'
        'ciDjgpLoh6rlt7Hmm7TmlrDjgZnjgovjgIIKCiAgICBkaXN0IHBheWxvYWQg44GuIGBfYm9vdHN0'
        'cmFwL2AgKG1heWF0b29sc191cGRhdGVyLnB5ICsgdXNlclNldHVwLnB5KSDjga4gQk9PVFNUUkFQ'
        'X1ZFUlNJT04g44GMCiAgICDotbDooYzkuK3jgojjgormlrDjgZfjgZHjgozjgbAgPGNhY2hlPi9i'
        'b290c3RyYXAvIOOBq+OCs+ODlOODvCDihpIgKirmrKHlm54gTWF5YSDotbfli5Xjgaflj43mmKAq'
        'KuOAguOBk+OCjOOBq+OCiOOCigogICAgdXBkYXRlciDjga7jg5DjgrDkv67mraPnrYnjgpLjgIxp'
        'bnN0YWxsLnB5IOOBruWGjeOCs+ODlOODmuOAjeOBquOBl+OBp+WFqCBQQyDjgavphY3jgozjgosg'
        'KD0g5YaN6YWN5biD5LiN6KaBKeOAggogICAgICAqIGNvbmZpZy5qc29uIOOBr+inpuOCieOBquOB'
        'hCAodG9rZW4g44KS5L+d5oyBKeOAggogICAgICAqIOWjiuOCjOOBn+eJiOOBp+ipsOOCgOOBruOC'
        'kumYsuOBkOOBn+OCgeOAgeWPluOCiui+vOOCgOWJjeOBqyBjb21waWxlIOaknOiovCArIOaXouWt'
        'mOOCkiAuYmFrIOOBq+mAgOmBv+OAggogICAgIiIiCiAgICBzcmNfZGlyID0gb3MucGF0aC5qb2lu'
        'KF9saXZlX3BhdGgoY2FjaGUpLCAiX2Jvb3RzdHJhcCIpCiAgICBzcmNfdXBkYXRlciA9IG9zLnBh'
        'dGguam9pbihzcmNfZGlyLCAibWF5YXRvb2xzX3VwZGF0ZXIucHkiKQogICAgaWYgbm90IG9zLnBh'
        'dGguaXNmaWxlKHNyY191cGRhdGVyKToKICAgICAgICByZXR1cm4KICAgIGJ1bmRsZWQgPSBfcGFy'
        'c2VfYm9vdHN0cmFwX3ZlcnNpb24oc3JjX3VwZGF0ZXIpCiAgICBpZiBidW5kbGVkIGlzIE5vbmUg'
        'b3IgYnVuZGxlZCA8PSBCT09UU1RSQVBfVkVSU0lPTjoKICAgICAgICByZXR1cm4KICAgIHRyeToK'
        'ICAgICAgICB3aXRoIG9wZW4oc3JjX3VwZGF0ZXIsICJyIiwgZW5jb2Rpbmc9InV0Zi04IikgYXMg'
        'ZjoKICAgICAgICAgICAgY29tcGlsZShmLnJlYWQoKSwgc3JjX3VwZGF0ZXIsICJleGVjIikgICAj'
        'IOWjiuOCjOOBnyB1cGRhdGVyIOOCkuWPluOCiui+vOOBvuOBquOBhOS/nemZugogICAgZXhjZXB0'
        'IEV4Y2VwdGlvbjoKICAgICAgICBfbG9nKCJib290c3RyYXAg6Ieq5bex5pu05paw44KS6KaL6YCB'
        '44KKICjmlrAgdXBkYXRlciDjgYwgY29tcGlsZSDkuI3lj68pOiB2JXMiICUgYnVuZGxlZCkKICAg'
        'ICAgICByZXR1cm4KICAgIGRzdF9kaXIgPSBvcy5wYXRoLmpvaW4oY2FjaGUsICJib290c3RyYXAi'
        'KQogICAgb3MubWFrZWRpcnMoZHN0X2RpciwgZXhpc3Rfb2s9VHJ1ZSkKICAgIGZvciBuYW1lIGlu'
        'ICgibWF5YXRvb2xzX3VwZGF0ZXIucHkiLCAidXNlclNldHVwLnB5Iik6CiAgICAgICAgc3AgPSBv'
        'cy5wYXRoLmpvaW4oc3JjX2RpciwgbmFtZSkKICAgICAgICBpZiBub3Qgb3MucGF0aC5pc2ZpbGUo'
        'c3ApOgogICAgICAgICAgICBjb250aW51ZQogICAgICAgIGRwID0gb3MucGF0aC5qb2luKGRzdF9k'
        'aXIsIG5hbWUpCiAgICAgICAgdHJ5OgogICAgICAgICAgICBpZiBvcy5wYXRoLmlzZmlsZShkcCk6'
        'CiAgICAgICAgICAgICAgICBzaHV0aWwuY29weTIoZHAsIGRwICsgIi5iYWsiKQogICAgICAgICAg'
        'ICBzaHV0aWwuY29weTIoc3AsIGRwKQogICAgICAgIGV4Y2VwdCBFeGNlcHRpb246CiAgICAgICAg'
        'ICAgIF9sb2coImJvb3RzdHJhcCDoh6rlt7Hmm7TmlrDjgafjgrPjg5Tjg7zlpLHmlZcgKCVzKTpc'
        'biVzIiAlIChuYW1lLCB0cmFjZWJhY2suZm9ybWF0X2V4YygpKSkKICAgICAgICAgICAgcmV0dXJu'
        'CiAgICBfbG9nKCJ1cGRhdGVyIOOCkuiHquW3seabtOaWsOOBl+OBvuOBl+OBnyAodiVzIC0+IHYl'
        'cynjgILmrKHlm54gTWF5YSDotbfli5Xjgaflj43mmKDjgZXjgozjgb7jgZnjgIIiCiAgICAgICAg'
        'ICUgKEJPT1RTVFJBUF9WRVJTSU9OLCBidW5kbGVkKSkKCgojIC0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLQoj'
        'IOWPluW+lyAoYmFja2dyb3VuZCB0aHJlYWTjgIJNYXlhIEFQSSDjga/op6bjgonjgarjgYQpCiMg'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tCmRlZiBjaGVja19hbmRfZG93bmxvYWQoY2ZnOiBkaWN0LCBjYWNo'
        'ZTogc3RyKSAtPiBOb25lOgogICAgcmVtb3RlID0gX3Jlc29sdmVfcmVtb3RlKGNmZykKICAgIHZl'
        'cnNpb24gPSByZW1vdGVbInZlcnNpb24iXQogICAgc3RhdGUgPSBfcmVhZF9zdGF0ZShjYWNoZSkK'
        'ICAgIGxpdmUgPSBfbGl2ZV9wYXRoKGNhY2hlKQogICAgbGl2ZV9vayA9IF9pc19saW5rKGxpdmUp'
        'IGFuZCBfaXNfdmFsaWRfcGF5bG9hZChsaXZlKQoKICAgIGlmIGxpdmVfb2sgYW5kIHN0YXRlLmdl'
        'dCgiYWN0aXZlIikgPT0gdmVyc2lvbiBhbmQgbm90IHN0YXRlLmdldCgicGVuZGluZyIpOgogICAg'
        'ICAgIF9sb2coIuacgOaWsOOBp+OBmSAoJXMpIiAlIHZlcnNpb25bOjE2XSkKICAgICAgICByZXR1'
        'cm4KCiAgICB2cCA9IF92ZXJzaW9uX3BhdGgoY2FjaGUsIHZlcnNpb24pCiAgICBpZiBub3QgX2lz'
        'X3ZhbGlkX3BheWxvYWQodnApOgogICAgICAgIF9sb2coIuaWsOODkOODvOOCuOODp+ODs+OCkuWP'
        'luW+l+OBl+OBvuOBmTogJXMiICUgdmVyc2lvbls6MTZdKQogICAgICAgIHRtcCA9IG9zLnBhdGgu'
        'am9pbihjYWNoZSwgInRtcCIpCiAgICAgICAgc2h1dGlsLnJtdHJlZShfbHAodG1wKSwgaWdub3Jl'
        'X2Vycm9ycz1UcnVlKQogICAgICAgIG9zLm1ha2VkaXJzKF9scCh0bXApLCBleGlzdF9vaz1UcnVl'
        'KQogICAgICAgIHppcHBhdGggPSBvcy5wYXRoLmpvaW4odG1wLCAiZG93bmxvYWQuemlwIikKICAg'
        'ICAgICBfZG93bmxvYWQocmVtb3RlWyJ1cmwiXSwgemlwcGF0aCwgY2ZnLmdldCgidG9rZW4iLCAi'
        'IiksIHJlbW90ZS5nZXQoImFjY2VwdCIsIEFDQ0VQVF9BUkNISVZFKSkKICAgICAgICB3aXRoIHpp'
        'cGZpbGUuWmlwRmlsZSh6aXBwYXRoKSBhcyB6OgogICAgICAgICAgICBpZiB6LnRlc3R6aXAoKSBp'
        'cyBub3QgTm9uZToKICAgICAgICAgICAgICAgIHJhaXNlIFJ1bnRpbWVFcnJvcigiemlwIOegtOaQ'
        'jSIpCiAgICAgICAgICAgIGV4ID0gb3MucGF0aC5qb2luKHRtcCwgImV4IikKICAgICAgICAgICAg'
        'b3MubWFrZWRpcnMoX2xwKGV4KSwgZXhpc3Rfb2s9VHJ1ZSkKICAgICAgICAgICAgei5leHRyYWN0'
        'YWxsKF9scChleCkpCiAgICAgICAgcm9vdCA9IF9mbGF0dGVuX3NpbmdsZV90b3AoZXgpCiAgICAg'
        'ICAgaWYgbm90IF9pc192YWxpZF9wYXlsb2FkKHJvb3QpOgogICAgICAgICAgICByYWlzZSBSdW50'
        'aW1lRXJyb3IoIuWPluW+l+eJqeOBqyAlcyDjgYzopovjgaTjgYvjgorjgb7jgZvjgpMiICUgU0VO'
        'VElORUwpCiAgICAgICAgb3MubWFrZWRpcnMoX2xwKF92ZXJzaW9uc19kaXIoY2FjaGUpKSwgZXhp'
        'c3Rfb2s9VHJ1ZSkKICAgICAgICBzaHV0aWwucm10cmVlKF9scCh2cCksIGlnbm9yZV9lcnJvcnM9'
        'VHJ1ZSkKICAgICAgICBzaHV0aWwubW92ZShfbHAocm9vdCksIF9scCh2cCkpCiAgICAgICAgc2h1'
        'dGlsLnJtdHJlZShfbHAodG1wKSwgaWdub3JlX2Vycm9ycz1UcnVlKQogICAgICAgIF9sb2coIuWP'
        'luW+l+WujOS6hjogJXMiICUgdmVyc2lvbls6MTZdKQoKICAgICMg5qyh5Zue6LW35YuV44Gn5Y+N'
        '5pigIChwZW5kaW5nIOOBq+epjeOCgCnjgILjgZ/jgaDjgZcgbGl2ZSDjgYznhKHjgZHjgozjgbDl'
        'jbPpgannlKggKOWIneWbninjgIIKICAgIHN0YXRlWyJwZW5kaW5nIl0gPSB2ZXJzaW9uCiAgICBf'
        'd3JpdGVfc3RhdGUoY2FjaGUsIHN0YXRlKQogICAgaWYgbm90IGxpdmVfb2s6CiAgICAgICAgYXBw'
        'bHlfcGVuZGluZyhjYWNoZSkKICAgIGVsc2U6CiAgICAgICAgX2xvZygi5qyh5ZueIE1heWEg6LW3'
        '5YuV44Gn5Y+N5pig44GV44KM44G+44GZOiAlcyIgJSB2ZXJzaW9uWzoxNl0pCgoKIyAtLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0KIyDjgqjjg7Pjg4jjg6rjg53jgqTjg7Pjg4gKIyAtLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0KZGVmIHJ1bihjb25maWdfcGF0aDogc3RyIHwgTm9uZSA9IE5vbmUsIGJsb2NraW5nOiBib29s'
        'ID0gRmFsc2UpIC0+IE5vbmU6CiAgICBnbG9iYWwgX0xPR19DQUNIRQogICAgdHJ5OgogICAgICAg'
        'IGNmZyA9IGxvYWRfY29uZmlnKGNvbmZpZ19wYXRoKQogICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBl'
        'OgogICAgICAgIF9sb2coImNvbmZpZy5qc29uIOiqrei+vOWkseaVlyAo5pyq6YWN572uPyk6ICVz'
        'IiAlIGUpCiAgICAgICAgcmV0dXJuCgogICAgcmF3ID0gY2ZnLmdldCgiY2FjaGVfZGlyIikKICAg'
        'IGNhY2hlID0gb3MucGF0aC5leHBhbmR2YXJzKG9zLnBhdGguZXhwYW5kdXNlcihyYXcpKSBpZiBy'
        'YXcgZWxzZSBkZWZhdWx0X2NhY2hlX2RpcigpCiAgICBfTE9HX0NBQ0hFID0gY2FjaGUKICAgIHRy'
        'eToKICAgICAgICBvcy5tYWtlZGlycyhfdmVyc2lvbnNfZGlyKGNhY2hlKSwgZXhpc3Rfb2s9VHJ1'
        'ZSkKICAgIGV4Y2VwdCBFeGNlcHRpb246CiAgICAgICAgX2xvZygi44Kt44Oj44OD44K344Ol5L2c'
        '5oiQ5aSx5pWXOlxuIiArIHRyYWNlYmFjay5mb3JtYXRfZXhjKCkpCiAgICAgICAgcmV0dXJuCgog'
        'ICAgIyDotbfli5Xjg4jjg6zjg7zjgrk6IHJ1bigpIOOBjOWRvOOBsOOCjOOBn+S6i+Wun+OBqOWI'
        'neacn+eKtuaFi+OCkuavjuWbniAxIOihjOaui+OBmeOAggogICAgIyAgIOi1t+WLleOBruOBn+OB'
        's+OBqyB1cGRhdGVyIOOBjOWun+mam+OBq+i1sOOBo+OBn+OBiyAvIHRva2Vu44O7YXV0aOODu2xp'
        'dmUg44KS44Gp44GG6KaL44Gm44GE44KL44GL44KSCiAgICAjICAgdXBkYXRlLmxvZyDjgafov73j'
        'gYjjgovjgojjgYbjgavjgZnjgosgKOOAjOWGjei1t+WLleOBl+OBn+OBruOBq+a2iOOBiOOBquOB'
        'hOOAjeOBruWIh+OCiuWIhuOBkeeUqCnjgIIKICAgIHRyeToKICAgICAgICBzdDAgPSBfcmVhZF9z'
        'dGF0ZShjYWNoZSkKICAgICAgICBsdiA9IF9saXZlX3BhdGgoY2FjaGUpCiAgICAgICAgX2xvZygi'
        '6LW35YuV44OB44Kn44OD44KvOiB1cGRhdGVyIHYlcyAvIHRva2VuPSVzIC8gYXV0aD0lcyAvIGxp'
        'dmU9JXMgLyBhY3RpdmU9JXMgLyBibG9ja2luZz0lcyIKICAgICAgICAgICAgICUgKEJPT1RTVFJB'
        'UF9WRVJTSU9OLAogICAgICAgICAgICAgICAgIuaciSIgaWYgKGNmZy5nZXQoInRva2VuIikgb3Ig'
        'IiIpLnN0cmlwKCkgZWxzZSAi54ShIiwKICAgICAgICAgICAgICAgIHN0MC5nZXQoImF1dGgiLCAi'
        '5pyqIiksCiAgICAgICAgICAgICAgICAi5pyJIiBpZiAoX2lzX2xpbmsobHYpIGFuZCBfaXNfdmFs'
        'aWRfcGF5bG9hZChsdikpIGVsc2UgIueEoSIsCiAgICAgICAgICAgICAgICBzdHIoc3QwLmdldCgi'
        'YWN0aXZlIikgb3IgIi0iKVs6MTZdLCBib29sKGJsb2NraW5nKSkpCiAgICBleGNlcHQgRXhjZXB0'
        'aW9uOgogICAgICAgIHBhc3MKCiAgICAjIDApIHRva2VuIOiqjeiovOOCsuODvOODiDogdG9rZW4g'
        '44GM54Sh44GR44KM44Gw44OE44O844OrIChsaXZlKSDjgpLlpJbjgZfjgabntYLkuoYgPSDjg4Tj'
        'g7zjg6vjgpLoqq3jgb/ovrzjgb7jgZvjgarjgYTjgIIKICAgIGlmIG5vdCBjZmcuZ2V0KCJ0b2tl'
        'biIpOgogICAgICAgIHRyeToKICAgICAgICAgICAgX3NldF90b29sc19lbmFibGVkKGNhY2hlLCBG'
        'YWxzZSkKICAgICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgICAgICBfbG9nKCLjg4Tjg7zj'
        'g6vnhKHlirnljJbjgafkvovlpJY6XG4iICsgdHJhY2ViYWNrLmZvcm1hdF9leGMoKSkKICAgICAg'
        'ICBfbG9nKCJ0b2tlbiDmnKroqK3lrpo6IOODhOODvOODq+OCkuiqreOBv+i+vOOBv+OBvuOBm+OC'
        'kyAobGl2ZSDjgpLlpJbjgZfjgb7jgZfjgZ8p44CCdG9rZW4g44KS6Kit5a6a44GX44GmIE1heWEg'
        '44KS5YaN6LW35YuV44GX44Gm44GP44Gg44GV44GE44CCIikKICAgICAgICByZXR1cm4KCiAgICAj'
        'IDAuNSkg5YmN5Zue44Gu6KqN6Ki857WQ5p6c44KS5ZCM5pyf44Gn5Y+N5pig44CCImZhaWwiICjl'
        'iY3lm54gNDAxKSDjgarjgokgKirjg4Tjg7zjg6vjgpLnhKHlirnljJbjgZfjgZ/jgb7jgb7jgIEK'
        'ICAgICMgICAgICBhcHBseV9wZW5kaW5nIC8g5YaN44Oq44Oz44KvIC8gc2VsZi11cGRhdGUg44KS'
        'IHNraXAqKiDjgZnjgovjgILjgZPjgozjgYznhKHjgYTjgaggYXBwbHlfcGVuZGluZyDjgoQKICAg'
        'ICMgICAgICBjaGVja19hbmRfZG93bmxvYWQg44Gu5YaN44Oq44Oz44Kv44GM54Sh5Yq5IHRva2Vu'
        'IOOBp+OCgiBsaXZlIOOCkuS9nOOCiuebtOOBl+OBpuOBl+OBvuOBhiAo5a6f5qmf44Gn55m655Sf'
        'KeOAggogICAgIyAgICAgIHRva2VuIOOBjOebtOOBo+OBpuOBhOOCjOOBsOS4i+OBriB3b3JrZXIg'
        '44GMIGNoZWNrIOaIkOWKn+aZguOBq+WGjeeiuuiqjeOBl+OBpuW+qeW4sOOBleOBm+OCi+OAggog'
        'ICAgaWYgX3JlYWRfc3RhdGUoY2FjaGUpLmdldCgiYXV0aCIpID09ICJmYWlsIjoKICAgICAgICB0'
        'cnk6CiAgICAgICAgICAgIF9zZXRfdG9vbHNfZW5hYmxlZChjYWNoZSwgRmFsc2UpCiAgICAgICAg'
        'ZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICAgICAgX2xvZygi44OE44O844Or54Sh5Yq55YyW44Gn'
        '5L6L5aSWOlxuIiArIHRyYWNlYmFjay5mb3JtYXRfZXhjKCkpCiAgICAgICAgX2xvZygi5YmN5Zue'
        'IHRva2VuIOiqjeiovOOBq+WkseaVl+OBl+OBpuOBhOOBvuOBmTog44OE44O844Or44Gv54Sh5Yq5'
        '44Gn44GZICjmnInlirnjgaogdG9rZW4g44Gr55u044GX44Gm5YaN6LW35YuV44Gn5b6p5biwKeOA'
        'giIpCiAgICBlbHNlOgogICAgICAgICMgMSkgcGVuZGluZyDjgpIgbGl2ZSDjgavpgannlKggKOiq'
        'jeiovCBPSyAvIOacqueiuuiqjeOBruOBqOOBjeOBruOBv+OAgmp1bmN0aW9uIOiyvOabv+OBquOB'
        'ruOBpyBsb2NrZWQg44Gn44KC5oiQ5YqfKQogICAgICAgIHRyeToKICAgICAgICAgICAgYXBwbHlf'
        'cGVuZGluZyhjYWNoZSkKICAgICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgICAgICBfbG9n'
        'KCJhcHBseV9wZW5kaW5nIOOBp+S+i+WkljpcbiIgKyB0cmFjZWJhY2suZm9ybWF0X2V4YygpKQog'
        'ICAgICAgICMgMS41KSBsaXZlIOOBq+WQjOaiseOBleOCjOOBn+aWsOOBl+OBhCBib290c3RyYXAg'
        '44GnIHVwZGF0ZXIg44KS6Ieq5bex5pu05pawIChpbnN0YWxsLnB5IOWGjemFjeW4g+S4jeimgeWM'
        'likKICAgICAgICB0cnk6CiAgICAgICAgICAgIF9yZWZyZXNoX2Jvb3RzdHJhcChjYWNoZSkKICAg'
        'ICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgICAgICBfbG9nKCJib290c3RyYXAg6Ieq5bex'
        '5pu05paw44Gn5L6L5aSWOlxuIiArIHRyYWNlYmFjay5mb3JtYXRfZXhjKCkpCiAgICAgICAgIyAy'
        'KSDlj6TjgYTniYjjg5Xjgqnjg6vjg4DjgpLmjoPpmaQgKGFjdGl2ZS9wZW5kaW5nIOOBr+aui+OB'
        'mSkKICAgICAgICB0cnk6CiAgICAgICAgICAgIHN0ID0gX3JlYWRfc3RhdGUoY2FjaGUpCiAgICAg'
        'ICAgICAgIF9jbGVhbnVwX3ZlcnNpb25zKGNhY2hlLCBhbHdheXNfa2VlcD0oc3QuZ2V0KCJhY3Rp'
        'dmUiKSwgc3QuZ2V0KCJwZW5kaW5nIikpKQogICAgICAgIGV4Y2VwdCBFeGNlcHRpb246CiAgICAg'
        'ICAgICAgIHBhc3MKCiAgICBpZiBub3QgY2ZnLmdldCgiZW5hYmxlZCIsIFRydWUpOgogICAgICAg'
        'IF9sb2coIuiHquWLleabtOaWsOOBr+eEoeWKueWMluOBleOCjOOBpuOBhOOBvuOBmSAoY29uZmln'
        'LmVuYWJsZWQ9ZmFsc2UpIikKICAgICAgICByZXR1cm4KCiAgICBpbnRlcnZhbCA9IGZsb2F0KGNm'
        'Zy5nZXQoImNoZWNrX2ludGVydmFsX2hvdXJzIiwgMCkgb3IgMCkgKiAzNjAwLjAKICAgIHN0YXRl'
        'ID0gX3JlYWRfc3RhdGUoY2FjaGUpCiAgICBpZiBpbnRlcnZhbCA+IDAgYW5kICh0aW1lLnRpbWUo'
        'KSAtIGZsb2F0KHN0YXRlLmdldCgibGFzdF9jaGVjayIsIDApKSkgPCBpbnRlcnZhbDoKICAgICAg'
        'ICBfbG9nKCLjg4Hjgqfjg4Pjgq/plpPpmpTlhoXjga7jgZ/jgoHmm7TmlrDnorroqo3jgpLjgrnj'
        'gq3jg4Pjg5ciKQogICAgICAgIHJldHVybgoKICAgIGRlZiB3b3JrZXIoKToKICAgICAgICB0cnk6'
        'CiAgICAgICAgICAgIGNoZWNrX2FuZF9kb3dubG9hZChjZmcsIGNhY2hlKQogICAgICAgICAgICAj'
        'IOiqjeiovCBPSyAoR2l0SHViIOOBq+WxiuOBhOOBnykg4oaSIOe1kOaenOOCkuS/neWtmOOBl+OD'
        'hOODvOODq+OCkuacieWKueWMliAo54Sh5Yq554q25oWL44GL44KJ44Gu5b6p5biw44KS5ZCr44KA'
        'KQogICAgICAgICAgICBfbWFya19hdXRoKGNhY2hlLCAib2siKQogICAgICAgICAgICB0cnk6CiAg'
        'ICAgICAgICAgICAgICBfc2V0X3Rvb2xzX2VuYWJsZWQoY2FjaGUsIFRydWUpCiAgICAgICAgICAg'
        'IGV4Y2VwdCBFeGNlcHRpb246CiAgICAgICAgICAgICAgICBfbG9nKCLjg4Tjg7zjg6vmnInlirnl'
        'jJbjgafkvovlpJY6XG4iICsgdHJhY2ViYWNrLmZvcm1hdF9leGMoKSkKICAgICAgICBleGNlcHQg'
        'dXJsbGliLmVycm9yLkhUVFBFcnJvciBhcyBlOgogICAgICAgICAgICBpZiBlLmNvZGUgPT0gNDAx'
        'OgogICAgICAgICAgICAgICAgIyDnhKHlirkgLyDlpLHlirkgLyByZXZva2Ug44GV44KM44GfIHRv'
        'a2VuID0g6KqN6Ki844Gq44GXIOKGkiDoqJjpjLLjgZfjgabjg4Tjg7zjg6vjgpLnhKHlirnljJYK'
        'ICAgICAgICAgICAgICAgIF9tYXJrX2F1dGgoY2FjaGUsICJmYWlsIikKICAgICAgICAgICAgICAg'
        'IHRyeToKICAgICAgICAgICAgICAgICAgICBfc2V0X3Rvb2xzX2VuYWJsZWQoY2FjaGUsIEZhbHNl'
        'KQogICAgICAgICAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICAgICAgICAgICAgICBw'
        'YXNzCiAgICAgICAgICAgICAgICBfbG9nKCJ0b2tlbiDoqo3oqLzlpLHmlZcgKDQwMSBCYWQgY3Jl'
        'ZGVudGlhbHMpOiDjg4Tjg7zjg6vjgpLnhKHlirnljJbjgZfjgb7jgZfjgZ/jgIIiCiAgICAgICAg'
        'ICAgICAgICAgICAgICLmnInlirnjgaogdG9rZW4g44Gr5beu44GX5pu/44GI44GmIE1heWEg44KS'
        '5YaN6LW35YuV44GX44Gm44GP44Gg44GV44GE44CCIikKICAgICAgICAgICAgZWxzZToKICAgICAg'
        'ICAgICAgICAgICMgNDAxIOS7peWkliAocmF0ZS1saW1pdC/mqKnpmZAv5LiA5pmC6Zqc5a6zKSDj'
        'ga/nhKHlirnljJbjgZfjgarjgYQgKOiqpOmBruaWreOCkumBv+OBkeOCiykKICAgICAgICAgICAg'
        'ICAgIHRyeToKICAgICAgICAgICAgICAgICAgICBib2R5ID0gZS5yZWFkKCkuZGVjb2RlKCJ1dGYt'
        'OCIsICJyZXBsYWNlIikuc3RyaXAoKVs6MzAwXQogICAgICAgICAgICAgICAgZXhjZXB0IEV4Y2Vw'
        'dGlvbjoKICAgICAgICAgICAgICAgICAgICBib2R5ID0gIiIKICAgICAgICAgICAgICAgIF9sb2co'
        'IuabtOaWsOODgeOCp+ODg+OCr+WkseaVlyAoSFRUUCAlcyAlcykuICVzJXMiCiAgICAgICAgICAg'
        'ICAgICAgICAgICUgKGUuY29kZSwgZS5yZWFzb24sIF9odHRwX2hpbnQoZS5jb2RlKSwgKCJcbiAg'
        'R2l0SHViOiAiICsgYm9keSkgaWYgYm9keSBlbHNlICIiKSkKICAgICAgICBleGNlcHQgRXhjZXB0'
        'aW9uOgogICAgICAgICAgICAjIOODjeODg+ODiOODr+ODvOOCr+manOWus+etieOBr+eEoeWKueWM'
        'luOBl+OBquOBhCAo44Kq44OV44Op44Kk44Oz5a6J5YWoKQogICAgICAgICAgICBfbG9nKCLmm7Tm'
        'lrDjg4Hjgqfjg4Pjgq/lpLHmlZc6XG4iICsgdHJhY2ViYWNrLmZvcm1hdF9leGMoKSkKICAgICAg'
        'ICBmaW5hbGx5OgogICAgICAgICAgICBzdDIgPSBfcmVhZF9zdGF0ZShjYWNoZSkKICAgICAgICAg'
        'ICAgc3QyWyJsYXN0X2NoZWNrIl0gPSB0aW1lLnRpbWUoKQogICAgICAgICAgICBfd3JpdGVfc3Rh'
        'dGUoY2FjaGUsIHN0MikKCiAgICBpZiBibG9ja2luZzoKICAgICAgICB3b3JrZXIoKQogICAgZWxz'
        'ZToKICAgICAgICB0aHJlYWRpbmcuVGhyZWFkKHRhcmdldD13b3JrZXIsIG5hbWU9Ik1heWFUb29s'
        'c1VwZGF0ZXIiLCBkYWVtb249VHJ1ZSkuc3RhcnQoKQo='
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


def _get_existing_token(cache_dir):
    """指定の置き場 (or 旧 modules) の既存 token 文字列を返す (無ければ '')。UI のヒント用。"""
    new_cache = _expand(cache_dir) if cache_dir else _default_cache()
    cands = [os.path.join(new_cache, "bootstrap", "config.json")]
    try:
        appdir, _ = _maya_dirs()
        cands.append(os.path.join(appdir, "modules", "MayaToolsBootstrap", "config.json"))
    except Exception:
        pass
    for c in cands:
        if os.path.isfile(c):
            try:
                t = (json.load(open(c, encoding="utf-8")).get("token") or "").strip()
                if t:
                    return t
            except Exception:
                pass
    return ""


def _check_token_validity(owner, repo, source_mode, ref, token):
    """GitHub に token の有効性を問い合わせる (UI のヒント用)。
    返り値: 'valid' / 'invalid'(401) / 'noaccess'(403/404) / 'unknown'(オフライン等) / 'none'。"""
    if not token:
        return "none"
    import urllib.request
    import urllib.error
    if source_mode == "release":
        url = "https://api.github.com/repos/%s/%s/releases/latest" % (owner, repo)
    else:
        url = "https://api.github.com/repos/%s/%s/commits/%s" % (owner, repo, ref or "main")
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "MayaTools-installer")
    try:
        urllib.request.urlopen(req, timeout=8).read(1)
        return "valid"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "invalid"
        if e.code in (403, 404):
            return "noaccess"
        return "unknown"
    except Exception:
        return "unknown"


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


def _apply_token(token, cache_dir, log):
    """既存インストールの token だけを更新し、認証確認してツールの有効/無効を反映する (軽量)。

    フル install と違い bootstrap の再配置や Maya.env 変更はしない。token を config に書いて
    updater を回すだけ。有効なら live が復活、無効ならツール無効のまま。返り値 dict。
    """
    new_cache = _expand(cache_dir) if cache_dir else _default_cache()
    cfg_path = os.path.join(new_cache, "bootstrap", "config.json")
    if not os.path.isfile(cfg_path):
        return {"ok": False, "reason": "no_install"}
    try:
        cfg = json.load(open(cfg_path, encoding="utf-8"))
    except Exception:
        return {"ok": False, "reason": "no_install"}
    if token:
        cfg["token"] = token
    if not (cfg.get("token") or "").strip():
        return {"ok": False, "reason": "no_token"}
    with open(cfg_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    log("トークンを更新しました。認証を確認中…")
    boot = os.path.join(new_cache, "bootstrap")
    if boot not in sys.path:
        sys.path.insert(0, boot)
    sys.modules.pop("mayatools_updater", None)
    import mayatools_updater
    mayatools_updater.run(cfg_path, blocking=True)   # 認証確認 → 有効化/無効化
    enabled = mayatools_updater._is_valid_payload(os.path.join(new_cache, "live"))
    return {"ok": True, "enabled": enabled}


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

    # --- パレット (scripts/mtui.py と同じ統一トークン。install.py は自己完結ゆえ値を複製) ---
    #   深さ3段: 背景#2b2b2b → カード#3a3a3a → 入力欄#2a2a2a(沈める)。青#4f8fd0 / 角丸4px。
    # インストーラは「外周(枠)=#3a3a3a / 中央カード=#2b2b2b」を **意図的に** 採用 (ツール群は逆)。
    #   理由: ツール(多ペイン)は #3a3a3a を panel/header(枠)に使う。インストーラは単一の中央ダイアログ
    #   なので #3a3a3a を外周(背景)に置く方が「枠が #3a3a3a」で揃って見える (中央に #3a3a3a だと浮く)。
    #   入れ替えで入力欄がカードと同色化するため、入力欄も一段暗く #242424 に沈ませる。
    #   ★ 一貫性のために bg=#2b2b2b へ戻さないこと (これは意図的・確認済の選択)。
    BG, CARD, FIELD = "#3a3a3a", "#2b2b2b", "#242424"
    FG, MUTE = "#e0e0e0", "#a0a0a0"
    LINE, DIVIDER = "#1f1f1f", "#555555"
    ACCENT, ACCENT_H = "#4f8fd0", "#5fa0e0"
    OKC, ERRC, LOGBG = "#4caf50", "#dc3545", "#1e1e1e"

    CSS = (
        "QDialog{background:%(BG)s;}"
        "QLabel{color:%(FG)s;font-size:12px;}"
        "QLabel#title{color:#ffffff;font-size:16px;font-weight:600;}"
        "QLabel#sub{color:%(MUTE)s;font-size:11px;}"
        "QLabel#flabel{color:%(MUTE)s;font-size:11px;}"
        "#card{background:%(CARD)s;border:1px solid %(LINE)s;border-radius:4px;}"
        "QLineEdit,QComboBox{background:%(FIELD)s;color:%(FG)s;border:1px solid %(LINE)s;"
        "border-radius:4px;padding:7px 9px;font-size:12px;selection-background-color:%(ACCENT)s;}"
        "QLineEdit:focus,QComboBox:focus{border:1px solid %(ACCENT)s;}"
        "QComboBox::drop-down{border:0;width:18px;}"
        "QPlainTextEdit{background:%(LOGBG)s;color:#c8ccd2;border:1px solid %(LINE)s;"
        "border-radius:4px;padding:6px;font-family:Consolas,'Courier New',monospace;font-size:11px;}"
        "QPushButton{background:transparent;color:%(MUTE)s;border:1px solid %(DIVIDER)s;"
        "border-radius:4px;padding:8px 16px;font-size:12px;}"
        "QPushButton:hover{color:%(FG)s;border-color:#6a6a6a;}"
        "QPushButton#primary{background:%(ACCENT)s;color:#ffffff;border:0;font-weight:600;padding:9px 20px;}"
        "QPushButton#primary:hover{background:%(ACCENT_H)s;}"
        "QPushButton#primary:disabled{background:#3a3a3a;color:#7d7d7d;}"
        "QToolButton{background:transparent;color:%(MUTE)s;border:0;font-size:11px;padding:2px;}"
        "QToolButton:hover{color:%(FG)s;}"
    ) % dict(BG=BG, CARD=CARD, FIELD=FIELD, FG=FG, MUTE=MUTE, LINE=LINE, DIVIDER=DIVIDER,
             ACCENT=ACCENT, ACCENT_H=ACCENT_H, LOGBG=LOGBG)

    dlg = QtWidgets.QDialog(_maya_main_window())
    dlg.setWindowTitle("MayaTools インストーラ")
    dlg.setStyleSheet(CSS)
    dlg.setMinimumWidth(470)
    root = QtWidgets.QVBoxLayout(dlg)
    root.setContentsMargins(22, 20, 22, 18)
    root.setSpacing(16)

    def _refit():
        # 展開/折りたたみ後にウィンドウを内容の高さへフィットし直す。
        # 直後だと layout が古い sizeHint を返し「折りたたんでも縮まない」(実機 Maya で発生)。
        # singleShot(0) で1フレーム遅延し、レイアウト確定後に縮める。
        def _do():
            dlg.setMinimumHeight(0)
            dlg.layout().invalidate()   # 古い sizeHint キャッシュを破棄 (実機でこれが無いと縮まない)
            dlg.layout().activate()
            dlg.resize(dlg.width(), dlg.sizeHint().height())
        QtCore.QTimer.singleShot(0, _do)

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
    hint_token = QtWidgets.QLabel(); hint_token.setWordWrap(True)
    cl.addWidget(hint_token)

    # cache
    cl.addWidget(_label("置き場 (ツールの保存先)"))
    ed_cache = QtWidgets.QLineEdit(defaults.get("cache_dir", "") or "~/dev/MayaTools")
    ed_cache.setPlaceholderText("空=%LOCALAPPDATA%\\MayaTools")
    cl.addWidget(ed_cache)

    # Token のヒント: 入力欄に値があればそれを、無ければ既存 token を、GitHub に問い合わせて
    # 「有効性」まで確認して出し分ける (✓有効 / ✗無効 / ⚠アクセス不可 / 確認中 / なし)。
    _tok_state = {"gen": 0, "label": "既存トークン"}

    def _hint(kind, text):
        col = {"ok": "#5fae7a", "err": "#e0574d", "warn": "#d8a23a", "mute": "#9a9a9a"}.get(kind, "#9a9a9a")
        hint_token.setStyleSheet("color:%s;font-size:11px;" % col)
        hint_token.setText(text)

    class _TokSig(QtCore.QObject):
        done = QtCore.Signal(int, str)
    _toksig = _TokSig()

    def _on_checked(gen, result):
        if gen != _tok_state["gen"]:
            return  # より新しい確認が走っているので破棄
        label = _tok_state["label"]
        keep = "（空欄で維持）" if label == "既存トークン" else ""
        if result == "valid":
            _hint("ok", "✓ %s は有効です%s" % (label, keep))
        elif result == "invalid":
            _hint("err", "✗ %s が無効です（失効/revoke 等）— 有効なトークンを入力してください" % label)
        elif result == "noaccess":
            _hint("warn", "⚠ %s はこの配布 repo にアクセスできません（権限/repo 名を確認）" % label)
        else:
            _hint("mute", "%s あり（有効性は未確認・オフライン）" % label)
    _toksig.done.connect(_on_checked)

    def _update_token_hint():
        _tok_state["gen"] += 1
        gen = _tok_state["gen"]
        typed = ed_token.text().strip()
        if typed:
            tok = typed; _tok_state["label"] = "入力したトークン"
            ed_token.setPlaceholderText("空のままなら既存のトークンを温存")
        else:
            tok = _get_existing_token(ed_cache.text().strip()); _tok_state["label"] = "既存トークン"
        if not tok:
            ed_token.setPlaceholderText("トークンを貼り付け（新規・必須）")
            _hint("warn", "⚠ トークンがありません — 入力しないとツールは読み込まれません")
            return
        _hint("mute", "🔍 %s を確認中…" % _tok_state["label"])
        args = (defaults.get("owner", ""), defaults.get("repo", ""),
                defaults.get("source_mode", "release"), defaults.get("ref", "main"), tok)

        def _work():
            try:
                r = _check_token_validity(*args)
            except Exception:
                r = "unknown"
            _toksig.done.emit(gen, r)
        import threading
        threading.Thread(target=_work, name="MTTokenCheck", daemon=True).start()

    ed_cache.editingFinished.connect(_update_token_hint)
    ed_token.editingFinished.connect(_update_token_hint)
    _update_token_hint()

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

    # --- フッター (閉じる左 / トークン適用・インストール右。主操作=インストールのみアクセント) ---
    # ※ stretch は入れない。内容にフィットさせる (_refit) ので、入れるとフッター上に隙間が出る。
    foot = QtWidgets.QHBoxLayout(); foot.setSpacing(8)
    btn_close = QtWidgets.QPushButton("閉じる")
    btn_close.setCursor(QtCore.Qt.PointingHandCursor)
    btn_apply = QtWidgets.QPushButton("トークンを適用")
    btn_apply.setCursor(QtCore.Qt.PointingHandCursor)
    btn_install = QtWidgets.QPushButton("インストール"); btn_install.setObjectName("primary")
    btn_install.setCursor(QtCore.Qt.PointingHandCursor)
    foot.addWidget(btn_close); foot.addStretch(1)
    foot.addWidget(btn_apply); foot.addWidget(btn_install)
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

    def _on_apply_token():
        btn_apply.setEnabled(False); btn_install.setEnabled(False)
        if not btn_log.isChecked():
            btn_log.setChecked(True)
        _set_status("run", "トークンを適用中…")
        _log("トークン適用を開始…")
        try:
            res = _apply_token(ed_token.text().strip(), ed_cache.text().strip(), _log)
            if not res.get("ok"):
                if res.get("reason") == "no_install":
                    _set_status("warn", "まだインストールされていません。先に［インストール］を実行してください。")
                else:
                    _set_status("warn", "トークンを入力してください。")
            elif res.get("enabled"):
                _set_status("ok", "✓ トークン有効 — ツールを有効化しました。Maya を再起動すると反映されます。")
            else:
                _set_status("err", "✗ トークンが無効です — ツールは無効のままです。有効なトークンを入力してください。")
        except Exception:
            import traceback
            _set_status("err", "✗ エラーが発生しました。ログを確認してください。")
            _log(traceback.format_exc())
        finally:
            btn_apply.setEnabled(True); btn_install.setEnabled(True)

    btn_install.clicked.connect(_on_install)
    btn_apply.clicked.connect(_on_apply_token)
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
