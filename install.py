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
        'ga7kv67mraMp44CCCiMgdjc6IHRva2VuIOacieWKueaAp+OCkuavjui1t+WLleOBp+eiuuiqjSAo'
        'Y2hlY2tfaW50ZXJ2YWxfaG91cnMg44Gv5pu05pawIERMIOOBruOBvyB0aHJvdHRsZeODu3Jldm9r'
        'ZSDjgpLplpPpmpTpnZ7kvp3lrZjjgafmpJzlh7op44CCCkJPT1RTVFJBUF9WRVJTSU9OID0gNwoK'
        'QUNDRVBUX0FTU0VUID0gImFwcGxpY2F0aW9uL29jdGV0LXN0cmVhbSIKQUNDRVBUX0FSQ0hJVkUg'
        'PSAiKi8qIgoKX0xPR19DQUNIRSA9IE5vbmUgICMgcnVuKCkg44Gn56K65a6aCgoKIyAtLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0KIyDjg5HjgrkgLyDjg63jgrAKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KZGVmIGRl'
        'ZmF1bHRfY2FjaGVfZGlyKCkgLT4gc3RyOgogICAgYmFzZSA9IG9zLmVudmlyb24uZ2V0KCJMT0NB'
        'TEFQUERBVEEiKQogICAgaWYgbm90IGJhc2U6CiAgICAgICAgYmFzZSA9IG9zLnBhdGguam9pbihv'
        'cy5wYXRoLmV4cGFuZHVzZXIoIn4iKSwgIi5sb2NhbCIsICJzaGFyZSIpCiAgICByZXR1cm4gb3Mu'
        'cGF0aC5qb2luKGJhc2UsICJNYXlhVG9vbHMiKQoKCmRlZiBfbHAocGF0aDogc3RyKSAtPiBzdHI6'
        'CiAgICAiIiJXaW5kb3dzIE1BWF9QQVRIKDI2MCkg5Zue6YG/44Gu6ZW344OR44K544OX44Os44OV'
        '44Kj44OD44Kv44K544CCIiIiCiAgICBpZiBvcy5uYW1lICE9ICJudCI6CiAgICAgICAgcmV0dXJu'
        'IHBhdGgKICAgIHAgPSBvcy5wYXRoLmFic3BhdGgocGF0aCkKICAgIGlmIHAuc3RhcnRzd2l0aCgi'
        'XFxcXD9cXCIpOgogICAgICAgIHJldHVybiBwCiAgICBpZiBwLnN0YXJ0c3dpdGgoIlxcXFwiKToK'
        'ICAgICAgICByZXR1cm4gIlxcXFw/XFxVTkNcXCIgKyBwWzI6XQogICAgcmV0dXJuICJcXFxcP1xc'
        'IiArIHAKCgpkZWYgX2xvZyhtc2c6IHN0cikgLT4gTm9uZToKICAgIHRleHQgPSAiW01heWFUb29s'
        'c10gIiArIHN0cihtc2cpCiAgICBjYWNoZSA9IF9MT0dfQ0FDSEUgb3IgZGVmYXVsdF9jYWNoZV9k'
        'aXIoKQogICAgdHJ5OgogICAgICAgIG9zLm1ha2VkaXJzKGNhY2hlLCBleGlzdF9vaz1UcnVlKQog'
        'ICAgICAgIHdpdGggb3Blbihvcy5wYXRoLmpvaW4oY2FjaGUsICJ1cGRhdGUubG9nIiksICJhIiwg'
        'ZW5jb2Rpbmc9InV0Zi04IikgYXMgZjoKICAgICAgICAgICAgZi53cml0ZSh0aW1lLnN0cmZ0aW1l'
        'KCIlWS0lbS0lZCAlSDolTTolUyAiKSArIHRleHQgKyAiXG4iKQogICAgZXhjZXB0IEV4Y2VwdGlv'
        'bjoKICAgICAgICBwYXNzCiAgICB0cnk6CiAgICAgICAgaWYgdGhyZWFkaW5nLmN1cnJlbnRfdGhy'
        'ZWFkKCkgaXMgdGhyZWFkaW5nLm1haW5fdGhyZWFkKCk6CiAgICAgICAgICAgIGZyb20gbWF5YS5h'
        'cGkuT3Blbk1heWEgaW1wb3J0IE1HbG9iYWwgICMgbm9xYTogUExDMDQxNQogICAgICAgICAgICBN'
        'R2xvYmFsLmRpc3BsYXlJbmZvKHRleHQpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHBh'
        'c3MKCgojIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLQojIOioreWumgojIC0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLQpk'
        'ZWYgbG9hZF9jb25maWcocGF0aDogc3RyIHwgTm9uZSA9IE5vbmUpIC0+IGRpY3Q6CiAgICBpZiBw'
        'YXRoIGlzIE5vbmU6CiAgICAgICAgcGF0aCA9IG9zLnBhdGguam9pbihvcy5wYXRoLmRpcm5hbWUo'
        'b3MucGF0aC5hYnNwYXRoKF9fZmlsZV9fKSksICJjb25maWcuanNvbiIpCiAgICB3aXRoIG9wZW4o'
        'cGF0aCwgInIiLCBlbmNvZGluZz0idXRmLTgiKSBhcyBmOgogICAgICAgIHJldHVybiBqc29uLmxv'
        'YWQoZikKCgojIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLQojIEhUVFAgKHByaXZhdGUgcmVwbzog44Ob44K5'
        '44OI44GM5aSJ44KP44KLIHJlZGlyZWN0IOOBp+OBryBBdXRob3JpemF0aW9uIOOCkuiQveOBqOOB'
        'mSkKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KY2xhc3MgX0F1dGhBd2FyZVJlZGlyZWN0KHVybGxpYi5y'
        'ZXF1ZXN0LkhUVFBSZWRpcmVjdEhhbmRsZXIpOgogICAgZGVmIHJlZGlyZWN0X3JlcXVlc3Qoc2Vs'
        'ZiwgcmVxLCBmcCwgY29kZSwgbXNnLCBoZWFkZXJzLCBuZXd1cmwpOgogICAgICAgIG5ldyA9IHN1'
        'cGVyKCkucmVkaXJlY3RfcmVxdWVzdChyZXEsIGZwLCBjb2RlLCBtc2csIGhlYWRlcnMsIG5ld3Vy'
        'bCkKICAgICAgICBpZiBuZXcgaXMgbm90IE5vbmU6CiAgICAgICAgICAgIHRyeToKICAgICAgICAg'
        'ICAgICAgIGlmIHVybGxpYi5wYXJzZS51cmxzcGxpdChyZXEuZnVsbF91cmwpLmhvc3RuYW1lICE9'
        'IHVybGxpYi5wYXJzZS51cmxzcGxpdChuZXd1cmwpLmhvc3RuYW1lOgogICAgICAgICAgICAgICAg'
        'ICAgIGZvciBrIGluIGxpc3QobmV3LmhlYWRlcnMua2V5cygpKToKICAgICAgICAgICAgICAgICAg'
        'ICAgICAgaWYgay5sb3dlcigpID09ICJhdXRob3JpemF0aW9uIjoKICAgICAgICAgICAgICAgICAg'
        'ICAgICAgICAgIGRlbCBuZXcuaGVhZGVyc1trXQogICAgICAgICAgICAgICAgICAgIG5ldy51bnJl'
        'ZGlyZWN0ZWRfaGRycy5wb3AoIkF1dGhvcml6YXRpb24iLCBOb25lKQogICAgICAgICAgICBleGNl'
        'cHQgRXhjZXB0aW9uOgogICAgICAgICAgICAgICAgcGFzcwogICAgICAgIHJldHVybiBuZXcKCgpk'
        'ZWYgX29wZW5lcigpOgogICAgcmV0dXJuIHVybGxpYi5yZXF1ZXN0LmJ1aWxkX29wZW5lcihfQXV0'
        'aEF3YXJlUmVkaXJlY3QoKSkKCgpkZWYgX3JlcXVlc3QodXJsOiBzdHIsIHRva2VuOiBzdHIsIGFj'
        'Y2VwdDogc3RyKSAtPiB1cmxsaWIucmVxdWVzdC5SZXF1ZXN0OgogICAgcmVxID0gdXJsbGliLnJl'
        'cXVlc3QuUmVxdWVzdCh1cmwpCiAgICByZXEuYWRkX2hlYWRlcigiVXNlci1BZ2VudCIsIFVTRVJf'
        'QUdFTlQpCiAgICByZXEuYWRkX2hlYWRlcigiQWNjZXB0IiwgYWNjZXB0KQogICAgaWYgdG9rZW46'
        'CiAgICAgICAgcmVxLmFkZF9oZWFkZXIoIkF1dGhvcml6YXRpb24iLCAiQmVhcmVyICIgKyB0b2tl'
        'bikKICAgIHJldHVybiByZXEKCgpkZWYgX2FwaV9qc29uKHVybDogc3RyLCB0b2tlbjogc3RyKSAt'
        'PiBkaWN0OgogICAgcmVxID0gX3JlcXVlc3QodXJsLCB0b2tlbiwgImFwcGxpY2F0aW9uL3ZuZC5n'
        'aXRodWIranNvbiIpCiAgICB3aXRoIF9vcGVuZXIoKS5vcGVuKHJlcSwgdGltZW91dD1BUElfVElN'
        'RU9VVCkgYXMgcjoKICAgICAgICByZXR1cm4ganNvbi5sb2FkcyhyLnJlYWQoKS5kZWNvZGUoInV0'
        'Zi04IikpCgoKZGVmIF9kb3dubG9hZCh1cmw6IHN0ciwgZGVzdDogc3RyLCB0b2tlbjogc3RyLCBh'
        'Y2NlcHQ6IHN0cikgLT4gTm9uZToKICAgICMgYWNjZXB0IOOBr+WPluW+l+eoruWIpeOBp+WkieOB'
        'iOOCizogYXNzZXQ9b2N0ZXQtc3RyZWFtIC8gemlwYmFsbD0qLyogKG9jdGV0IOOBoOOBqCA0MTUp'
        '44CCCiAgICByZXEgPSBfcmVxdWVzdCh1cmwsIHRva2VuLCBhY2NlcHQpCiAgICB3aXRoIF9vcGVu'
        'ZXIoKS5vcGVuKHJlcSwgdGltZW91dD1ET1dOTE9BRF9USU1FT1VUKSBhcyByLCBvcGVuKGRlc3Qs'
        'ICJ3YiIpIGFzIGY6CiAgICAgICAgc2h1dGlsLmNvcHlmaWxlb2JqKHIsIGYsIGxlbmd0aD0yNTYg'
        'KiAxMDI0KQoKCmRlZiBfaHR0cF9oaW50KGNvZGU6IGludCkgLT4gc3RyOgogICAgaWYgY29kZSA9'
        'PSA0MDE6CiAgICAgICAgcmV0dXJuICLjg4jjg7zjgq/jg7PjgYznhKHlirkv5pyf6ZmQ5YiH44KM'
        '44Gu5Y+v6IO95oCnIChjb25maWcuanNvbiDjga4gdG9rZW4g44KS56K66KqNKSIKICAgIGlmIGNv'
        'ZGUgPT0gNDAzOgogICAgICAgIHJldHVybiAoIuaoqemZkOS4jei2syBvciDjg6zjg7zjg4jliLbp'
        'mZDjgIJmaW5lLWdyYWluZWQgUEFUIOOBriBSZXBvc2l0b3J5IGFjY2VzcyDjgavlr77osaEgcmVw'
        'byDjgpLlkKvjgoHjgIEiCiAgICAgICAgICAgICAgICAiQ29udGVudHM9UmVhZCDjgpLku5jkuI7j'
        'gZfjgabjgYTjgovjgYvnorroqo0gKGNsYXNzaWMgdG9rZW4g44Gq44KJIHJlcG8g44K544Kz44O8'
        '44OXKSIpCiAgICBpZiBjb2RlID09IDQwNDoKICAgICAgICByZXR1cm4gIm93bmVyL3JlcG8vcmVm'
        'L3NvdXJjZV9tb2RlIOOCkueiuuiqjSAocHJpdmF0ZSDjgacgdG9rZW4g44GM44Gd44GuIHJlcG8g'
        '44KS6KaL44KJ44KM44Gq44GE5aC05ZCI44KCIDQwNCkiCiAgICByZXR1cm4gInRva2VuL293bmVy'
        'L3JlcG8vc291cmNlX21vZGUg44KS56K66KqNIgoKCmRlZiBfcmVzb2x2ZV9yZW1vdGUoY2ZnOiBk'
        'aWN0KSAtPiBkaWN0OgogICAgIiIieyJ2ZXJzaW9uIiwgInVybCIsICJhY2NlcHQifSDjgpLov5Tj'
        'gZnjgILlpLHmlZfmmYLjga/kvovlpJbjgIIiIiIKICAgIG93bmVyLCByZXBvLCB0b2tlbiA9IGNm'
        'Z1sib3duZXIiXSwgY2ZnWyJyZXBvIl0sIGNmZy5nZXQoInRva2VuIiwgIiIpCiAgICBtb2RlID0g'
        'Y2ZnLmdldCgic291cmNlX21vZGUiLCAicmVsZWFzZSIpCiAgICBpZiBtb2RlID09ICJyZWxlYXNl'
        'IjoKICAgICAgICBkYXRhID0gX2FwaV9qc29uKGYie0FQSV9ST09UfS9yZXBvcy97b3duZXJ9L3ty'
        'ZXBvfS9yZWxlYXNlcy9sYXRlc3QiLCB0b2tlbikKICAgICAgICB2ZXJzaW9uID0gZGF0YS5nZXQo'
        'InRhZ19uYW1lIikgb3IgZGF0YS5nZXQoIm5hbWUiKSBvciAiIgogICAgICAgIGZvciBhIGluIGRh'
        'dGEuZ2V0KCJhc3NldHMiLCBbXSk6CiAgICAgICAgICAgIGlmIHN0cihhLmdldCgibmFtZSIsICIi'
        'KSkubG93ZXIoKS5lbmRzd2l0aCgiLnppcCIpOgogICAgICAgICAgICAgICAgcmV0dXJuIHsidmVy'
        'c2lvbiI6IHZlcnNpb24sICJ1cmwiOiBhWyJ1cmwiXSwgImFjY2VwdCI6IEFDQ0VQVF9BU1NFVH0K'
        'ICAgICAgICByZXR1cm4geyJ2ZXJzaW9uIjogdmVyc2lvbiwgInVybCI6IGRhdGFbInppcGJhbGxf'
        'dXJsIl0sICJhY2NlcHQiOiBBQ0NFUFRfQVJDSElWRX0KICAgIHJlZiA9IGNmZy5nZXQoInJlZiIs'
        'ICJtYWluIikKICAgIGRhdGEgPSBfYXBpX2pzb24oZiJ7QVBJX1JPT1R9L3JlcG9zL3tvd25lcn0v'
        'e3JlcG99L2NvbW1pdHMve3JlZn0iLCB0b2tlbikKICAgIHJldHVybiB7InZlcnNpb24iOiBkYXRh'
        'WyJzaGEiXSwKICAgICAgICAgICAgInVybCI6IGYie0FQSV9ST09UfS9yZXBvcy97b3duZXJ9L3ty'
        'ZXBvfS96aXBiYWxsL3tyZWZ9IiwKICAgICAgICAgICAgImFjY2VwdCI6IEFDQ0VQVF9BUkNISVZF'
        'fQoKCiMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tCiMg44Kt44Oj44OD44K344OlIC8g54mIIC8ganVuY3Rp'
        'b24KIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KZGVmIF9zYWZlX3RhZyh0YWc6IHN0cikgLT4gc3RyOgog'
        'ICAgcmV0dXJuICIiLmpvaW4oYyBpZiAoYy5pc2FsbnVtKCkgb3IgYyBpbiAiLl8tIikgZWxzZSAi'
        'XyIgZm9yIGMgaW4gc3RyKHRhZykpCgoKZGVmIF92ZXJzaW9uc19kaXIoY2FjaGU6IHN0cikgLT4g'
        'c3RyOgogICAgcmV0dXJuIG9zLnBhdGguam9pbihjYWNoZSwgInZlcnNpb25zIikKCgpkZWYgX3Zl'
        'cnNpb25fcGF0aChjYWNoZTogc3RyLCB0YWc6IHN0cikgLT4gc3RyOgogICAgcmV0dXJuIG9zLnBh'
        'dGguam9pbihfdmVyc2lvbnNfZGlyKGNhY2hlKSwgX3NhZmVfdGFnKHRhZykpCgoKZGVmIF9saXZl'
        'X3BhdGgoY2FjaGU6IHN0cikgLT4gc3RyOgogICAgcmV0dXJuIG9zLnBhdGguam9pbihjYWNoZSwg'
        'TElWRSkKCgpkZWYgX2lzX3ZhbGlkX3BheWxvYWQocm9vdDogc3RyKSAtPiBib29sOgogICAgcmV0'
        'dXJuIG9zLnBhdGguaXNmaWxlKG9zLnBhdGguam9pbihyb290LCBTRU5USU5FTCkpCgoKZGVmIF9p'
        'c19saW5rKHBhdGg6IHN0cikgLT4gYm9vbDoKICAgICIiInBhdGgg44GMIGp1bmN0aW9uL3N5bWxp'
        'bmsgKHJlcGFyc2UgcG9pbnQpIOOBi+OAgiIiIgogICAgdHJ5OgogICAgICAgIGlmIG9zLnBhdGgu'
        'aXNsaW5rKHBhdGgpOgogICAgICAgICAgICByZXR1cm4gVHJ1ZQogICAgICAgIHJldHVybiBvcy5w'
        'YXRoLmlzZGlyKHBhdGgpIGFuZCBib29sKGdldGF0dHIob3MubHN0YXQocGF0aCksICJzdF9yZXBh'
        'cnNlX3RhZyIsIDApKQogICAgZXhjZXB0IE9TRXJyb3I6CiAgICAgICAgcmV0dXJuIEZhbHNlCgoK'
        'ZGVmIF9yZW1vdmVfbGluayhwYXRoOiBzdHIpIC0+IE5vbmU6CiAgICAiIiJqdW5jdGlvbi9zeW1s'
        'aW5rIOOCkuOAgeOCv+ODvOOCsuODg+ODiOOBq+inpuOCjOOBmuOBq+WkluOBmeOAgiIiIgogICAg'
        'aWYgbm90IG9zLnBhdGgubGV4aXN0cyhwYXRoKToKICAgICAgICByZXR1cm4KICAgIHRyeToKICAg'
        'ICAgICBvcy5ybWRpcihwYXRoKSAgICAgICAgIyBqdW5jdGlvbiDjga/jgZPjgozjgaflpJbjgozj'
        'gosgKOOCv+ODvOOCsuODg+ODiOOBruS4rei6q+OBr+a2iOOBiOOBquOBhCkKICAgIGV4Y2VwdCBP'
        'U0Vycm9yOgogICAgICAgIHRyeToKICAgICAgICAgICAgb3MudW5saW5rKHBhdGgpCiAgICAgICAg'
        'ZXhjZXB0IE9TRXJyb3I6CiAgICAgICAgICAgIHBhc3MKCgpkZWYgX21ha2VfanVuY3Rpb24obGlu'
        'azogc3RyLCB0YXJnZXQ6IHN0cikgLT4gTm9uZToKICAgICIiImxpbmsg44KSIGp1bmN0aW9uIOOB'
        'qOOBl+OBpiB0YXJnZXQg44Gr5ZCR44GR44KLICjml6LlrZggbGluayDjga/lpJbjgZkp44CCbG9j'
        'a2VkIOOBp+OCguaIkOWKn+OAgiIiIgogICAgaWYgb3MubmFtZSA9PSAibnQiOgogICAgICAgICMg'
        'Y21kIOOBriBta2xpbmsg44GvIGJhY2tzbGFzaCDlv4XpoIjjgIIiQzovVXNlcnMvLi4uIiDjgaDj'
        'gaggL1VzZXJzIOOCkuOCueOCpOODg+ODgeOBqOiqpOiqjeOBmeOCi+OAggogICAgICAgIGxpbmsg'
        'PSBvcy5wYXRoLm5vcm1wYXRoKGxpbmspCiAgICAgICAgdGFyZ2V0ID0gb3MucGF0aC5ub3JtcGF0'
        'aCh0YXJnZXQpCiAgICBfcmVtb3ZlX2xpbmsobGluaykKICAgIGlmIG9zLm5hbWUgPT0gIm50IjoK'
        'ICAgICAgICAjIGJ5dGVzIOOBp+WPluW+lyAoY21kIOOBryBDUDkzMiDlh7rlipvjgarjga7jgacg'
        'dGV4dD1UcnVlIOOBoOOBqCByZWFkZXIgdGhyZWFkIOOBjCBkZWNvZGUg5L6L5aSWKQogICAgICAg'
        'IHIgPSBzdWJwcm9jZXNzLnJ1bihbImNtZCIsICIvYyIsICJta2xpbmsiLCAiL0oiLCBsaW5rLCB0'
        'YXJnZXRdLCBjYXB0dXJlX291dHB1dD1UcnVlKQogICAgICAgIGlmIHIucmV0dXJuY29kZSAhPSAw'
        'IG9yIG5vdCBvcy5wYXRoLmlzZGlyKGxpbmspOgogICAgICAgICAgICBtc2cgPSAoci5zdGRlcnIg'
        'b3Igci5zdGRvdXQgb3IgYiIiKS5kZWNvZGUoImNwOTMyIiwgInJlcGxhY2UiKS5zdHJpcCgpCiAg'
        'ICAgICAgICAgIHJhaXNlIE9TRXJyb3IoImp1bmN0aW9uIOS9nOaIkOWkseaVlzogJXMgLT4gJXMg'
        'OiAlcyIgJSAobGluaywgdGFyZ2V0LCBtc2cpKQogICAgZWxzZToKICAgICAgICBvcy5zeW1saW5r'
        'KHRhcmdldCwgbGluaywgdGFyZ2V0X2lzX2RpcmVjdG9yeT1UcnVlKQoKCmRlZiBfcmVhZF9zdGF0'
        'ZShjYWNoZTogc3RyKSAtPiBkaWN0OgogICAgdHJ5OgogICAgICAgIHdpdGggb3Blbihvcy5wYXRo'
        'LmpvaW4oY2FjaGUsICJzdGF0ZS5qc29uIiksICJyIiwgZW5jb2Rpbmc9InV0Zi04IikgYXMgZjoK'
        'ICAgICAgICAgICAgcmV0dXJuIGpzb24ubG9hZChmKQogICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAg'
        'ICAgICByZXR1cm4ge30KCgpkZWYgX3dyaXRlX3N0YXRlKGNhY2hlOiBzdHIsIHN0YXRlOiBkaWN0'
        'KSAtPiBOb25lOgogICAgdHJ5OgogICAgICAgIHdpdGggb3Blbihvcy5wYXRoLmpvaW4oY2FjaGUs'
        'ICJzdGF0ZS5qc29uIiksICJ3IiwgZW5jb2Rpbmc9InV0Zi04IikgYXMgZjoKICAgICAgICAgICAg'
        'anNvbi5kdW1wKHN0YXRlLCBmLCBlbnN1cmVfYXNjaWk9RmFsc2UsIGluZGVudD0yKQogICAgZXhj'
        'ZXB0IEV4Y2VwdGlvbjoKICAgICAgICBfbG9nKCJzdGF0ZS5qc29uIOabuOi+vOWkseaVlzpcbiIg'
        'KyB0cmFjZWJhY2suZm9ybWF0X2V4YygpKQoKCmRlZiBfZmxhdHRlbl9zaW5nbGVfdG9wKGV4dHJh'
        'Y3RfZGlyOiBzdHIpIC0+IHN0cjoKICAgIGVudHJpZXMgPSBvcy5saXN0ZGlyKGV4dHJhY3RfZGly'
        'KQogICAgaWYgbGVuKGVudHJpZXMpID09IDE6CiAgICAgICAgaW5uZXIgPSBvcy5wYXRoLmpvaW4o'
        'ZXh0cmFjdF9kaXIsIGVudHJpZXNbMF0pCiAgICAgICAgaWYgb3MucGF0aC5pc2Rpcihpbm5lcik6'
        'CiAgICAgICAgICAgIHJldHVybiBpbm5lcgogICAgcmV0dXJuIGV4dHJhY3RfZGlyCgoKZGVmIF9j'
        'bGVhbnVwX3ZlcnNpb25zKGNhY2hlOiBzdHIsIGFsd2F5c19rZWVwKSAtPiBOb25lOgogICAgIiIi'
        '54mI44OV44Kp44Or44OA44KS5Y+k44GE44KC44Gu44GL44KJ5o6D6ZmkIChLRUVQX1JFQ0VOVCDk'
        'u7YgKyBhbHdheXNfa2VlcCDjga/mrovjgZkp44CCbG9ja2VkIOOBr+eEoeimluOAgiIiIgogICAg'
        'dmQgPSBfdmVyc2lvbnNfZGlyKGNhY2hlKQogICAgaWYgbm90IG9zLnBhdGguaXNkaXIodmQpOgog'
        'ICAgICAgIHJldHVybgogICAga2VlcCA9IHtfc2FmZV90YWcodCkgZm9yIHQgaW4gYWx3YXlzX2tl'
        'ZXAgaWYgdH0KICAgIGRpcnMgPSBzb3J0ZWQoZCBmb3IgZCBpbiBvcy5saXN0ZGlyKHZkKSBpZiBv'
        'cy5wYXRoLmlzZGlyKG9zLnBhdGguam9pbih2ZCwgZCkpKQogICAgIyB0YWcg44GvIGRpc3QtWVlZ'
        'WU1NREQtSEhNTVNTIOOBp+aYh+mghj3mmYLns7vliJfjgILmlrDjgZfjgYQgS0VFUF9SRUNFTlQg'
        '5Lu244Gv5q6L44GZ44CCCiAgICBmb3IgZCBpbiBkaXJzWzotS0VFUF9SRUNFTlRdIGlmIGxlbihk'
        'aXJzKSA+IEtFRVBfUkVDRU5UIGVsc2UgW106CiAgICAgICAgaWYgZCBpbiBrZWVwOgogICAgICAg'
        'ICAgICBjb250aW51ZQogICAgICAgIHNodXRpbC5ybXRyZWUoX2xwKG9zLnBhdGguam9pbih2ZCwg'
        'ZCkpLCBpZ25vcmVfZXJyb3JzPVRydWUpCgoKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KIyDpgannlKgg'
        'KGxpdmUganVuY3Rpb24g44Gu6LK85pu/KSDigJQgbG9ja2VkIOOBp+OCguaIkOWKnwojIC0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLQpkZWYgYXBwbHlfcGVuZGluZyhjYWNoZTogc3RyKSAtPiBib29sOgogICAg'
        'IiIic3RhdGUucGVuZGluZyDjgYzjgYLjgozjgbAgbGl2ZSDjgpIgdmVyc2lvbnMvPHBlbmRpbmc+'
        'IOOBuOiyvOOCiuabv+OBiOOCi+OAgiIiIgogICAgc3RhdGUgPSBfcmVhZF9zdGF0ZShjYWNoZSkK'
        'ICAgIHBlbmRpbmcgPSBzdGF0ZS5nZXQoInBlbmRpbmciKQogICAgaWYgbm90IHBlbmRpbmc6CiAg'
        'ICAgICAgcmV0dXJuIEZhbHNlCiAgICB2cCA9IF92ZXJzaW9uX3BhdGgoY2FjaGUsIHBlbmRpbmcp'
        'CiAgICBpZiBub3QgX2lzX3ZhbGlkX3BheWxvYWQodnApOgogICAgICAgIHN0YXRlWyJwZW5kaW5n'
        'Il0gPSBOb25lCiAgICAgICAgX3dyaXRlX3N0YXRlKGNhY2hlLCBzdGF0ZSkKICAgICAgICByZXR1'
        'cm4gRmFsc2UKICAgIHRyeToKICAgICAgICBfbWFrZV9qdW5jdGlvbihfbGl2ZV9wYXRoKGNhY2hl'
        'KSwgdnApCiAgICBleGNlcHQgT1NFcnJvciBhcyBlOgogICAgICAgIF9sb2coImxpdmUg5YiH5pu/'
        '44Gr5aSx5pWXICjmrKHlm57lho3oqabooYwpOiAlcyIgJSBlKQogICAgICAgIHJldHVybiBGYWxz'
        'ZQogICAgc3RhdGVbImFjdGl2ZSJdID0gcGVuZGluZwogICAgc3RhdGVbInBlbmRpbmciXSA9IE5v'
        'bmUKICAgIF93cml0ZV9zdGF0ZShjYWNoZSwgc3RhdGUpCiAgICBfbG9nKCLmm7TmlrDjgpLpgann'
        'lKjjgZfjgb7jgZfjgZ8gKGxpdmUgLT4gJXMpIiAlIHN0cihwZW5kaW5nKVs6MTZdKQogICAgcmV0'
        'dXJuIFRydWUKCgpkZWYgX3NldF90b29sc19lbmFibGVkKGNhY2hlOiBzdHIsIGVuYWJsZWQ6IGJv'
        'b2wpIC0+IE5vbmU6CiAgICAiIiJ0b2tlbiDjga7mnInnhKHjgavlv5zjgZjjgabjg4Tjg7zjg6sg'
        'KGxpdmUganVuY3Rpb24pIOOCkuacieWKuS/nhKHlirnljJbjgZnjgovjgIIKCiAgICB0b2tlbiDo'
        'qo3oqLzjgYznhKHjgYTjgajjgY3jga/jg4Tjg7zjg6vjgpLoqq3jgb/ovrzjgb7jgZvjgarjgYTm'
        'lrnph53jgIJNYXlhIOOBryA8Y2FjaGU+L2xpdmUg44KSCiAgICBNQVlBX01PRFVMRV9QQVRIIOe1'
        'jOeUseOBp+ODreODvOODieOBmeOCi+OBruOBp+OAgSoqbGl2ZSDjgpLlpJbjgZvjgbAgTWF5YSDj'
        'ga/jg4Tjg7zjg6vjgpLopovjgaTjgZHjgonjgozjgarjgYQqKgogICAgKOWPjeaYoOOBr+asoeWb'
        'nui1t+WLlSnjgILmnInlirnljJbjga8gbGl2ZSDjgYznhKHjgY8gYWN0aXZlIOeJiOOBjOOBguOC'
        'jOOBsOiyvOOCiuebtOOBmSAo54Sh5Yq554q25oWL44GL44KJ44Gu5b6p5biw44O744ON44OD44OI'
        '5LiN6KaBKeOAggogICAgIiIiCiAgICBsaXZlID0gX2xpdmVfcGF0aChjYWNoZSkKICAgIGlmIG5v'
        'dCBlbmFibGVkOgogICAgICAgIGlmIF9pc19saW5rKGxpdmUpOgogICAgICAgICAgICBfcmVtb3Zl'
        'X2xpbmsobGl2ZSkKICAgICAgICByZXR1cm4KICAgIGlmIF9pc19saW5rKGxpdmUpIGFuZCBfaXNf'
        'dmFsaWRfcGF5bG9hZChsaXZlKToKICAgICAgICByZXR1cm4gICMg5pei44Gr5pyJ5Yq5CiAgICBh'
        'Y3RpdmUgPSBfcmVhZF9zdGF0ZShjYWNoZSkuZ2V0KCJhY3RpdmUiKQogICAgaWYgYWN0aXZlOgog'
        'ICAgICAgIHZwID0gX3ZlcnNpb25fcGF0aChjYWNoZSwgYWN0aXZlKQogICAgICAgIGlmIF9pc192'
        'YWxpZF9wYXlsb2FkKHZwKToKICAgICAgICAgICAgdHJ5OgogICAgICAgICAgICAgICAgX21ha2Vf'
        'anVuY3Rpb24obGl2ZSwgdnApCiAgICAgICAgICAgICAgICBfbG9nKCLjg4Tjg7zjg6vjgpLmnInl'
        'irnljJbjgZfjgb7jgZfjgZ8gKGxpdmUgLT4gJXMpIiAlIHN0cihhY3RpdmUpWzoxNl0pCiAgICAg'
        'ICAgICAgIGV4Y2VwdCBPU0Vycm9yIGFzIGU6CiAgICAgICAgICAgICAgICBfbG9nKCLjg4Tjg7zj'
        'g6vmnInlirnljJbjgavlpLHmlZcgKOasoeWbnuWGjeippuihjCk6ICVzIiAlIGUpCgoKZGVmIF9t'
        'YXJrX2F1dGgoY2FjaGU6IHN0ciwgdmFsdWU6IHN0cikgLT4gTm9uZToKICAgICIiIuebtOi/keOB'
        'ruiqjeiovOe1kOaenOOCkiBzdGF0ZVsnYXV0aCddIOOBq+S/neWtmCAoJ29rJy8nZmFpbCcp44CC'
        'cnVuIOWGkumgreOBp+WQjOacn+eahOOBq+WPgueFp+OBl+OBpgogICAgJ2ZhaWwnIOOBquOCiSBs'
        'aXZlIOOCkuWkluOBl+OBn+OBvuOBviBhcHBseSDjgoLjgZfjgarjgYQgKD0g54Sh5Yq5IHRva2Vu'
        'IOOBpyBsaXZlIOOBjOWGjeeUn+aIkOOBleOCjOOCi+OBruOCkumYsuOBkCnjgIIiIiIKICAgIHRy'
        'eToKICAgICAgICBzdCA9IF9yZWFkX3N0YXRlKGNhY2hlKQogICAgICAgIHN0WyJhdXRoIl0gPSB2'
        'YWx1ZQogICAgICAgIF93cml0ZV9zdGF0ZShjYWNoZSwgc3QpCiAgICBleGNlcHQgRXhjZXB0aW9u'
        'OgogICAgICAgIHBhc3MKCgojIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLQojIGJvb3RzdHJhcCAodXBkYXRl'
        'ciDoh6rouqspIOOBruiHquW3seabtOaWsCDigJQgaW5zdGFsbC5weSDjgpLlho3phY3luIPjgZvj'
        'gZrjgasgdXBkYXRlciDjgpLmm7TmlrDjgZnjgosKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KZGVmIF9w'
        'YXJzZV9ib290c3RyYXBfdmVyc2lvbihweV9wYXRoOiBzdHIpOgogICAgIiIi44OV44Kh44Kk44Or'
        '44GL44KJIEJPT1RTVFJBUF9WRVJTSU9OIOOBruWApOOCkuODhuOCreOCueODiOino+aekOOBp+iq'
        'reOCgCAoaW1wb3J0IOOBr+OBl+OBquOBhCnjgIIiIiIKICAgIGltcG9ydCByZQogICAgdHJ5Ogog'
        'ICAgICAgIHdpdGggb3BlbihweV9wYXRoLCAiciIsIGVuY29kaW5nPSJ1dGYtOCIsIGVycm9ycz0i'
        'aWdub3JlIikgYXMgZjoKICAgICAgICAgICAgZm9yIGxpbmUgaW4gZjoKICAgICAgICAgICAgICAg'
        'IG0gPSByZS5tYXRjaChyIlxzKkJPT1RTVFJBUF9WRVJTSU9OXHMqPVxzKihcZCspIiwgbGluZSkK'
        'ICAgICAgICAgICAgICAgIGlmIG06CiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIGludChtLmdy'
        'b3VwKDEpKQogICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICBwYXNzCiAgICByZXR1cm4gTm9u'
        'ZQoKCmRlZiBfcmVmcmVzaF9ib290c3RyYXAoY2FjaGU6IHN0cikgLT4gTm9uZToKICAgICIiImxp'
        'dmUgKOmBqeeUqOa4iOOBrueJiCkg44Gr5ZCM5qKx44GV44KM44Gf5paw44GX44GEIGJvb3RzdHJh'
        'cCDjgYzjgYLjgozjgbAgdXBkYXRlciDjgpLoh6rlt7Hmm7TmlrDjgZnjgovjgIIKCiAgICBkaXN0'
        'IHBheWxvYWQg44GuIGBfYm9vdHN0cmFwL2AgKG1heWF0b29sc191cGRhdGVyLnB5ICsgdXNlclNl'
        'dHVwLnB5KSDjga4gQk9PVFNUUkFQX1ZFUlNJT04g44GMCiAgICDotbDooYzkuK3jgojjgormlrDj'
        'gZfjgZHjgozjgbAgPGNhY2hlPi9ib290c3RyYXAvIOOBq+OCs+ODlOODvCDihpIgKirmrKHlm54g'
        'TWF5YSDotbfli5Xjgaflj43mmKAqKuOAguOBk+OCjOOBq+OCiOOCigogICAgdXBkYXRlciDjga7j'
        'g5DjgrDkv67mraPnrYnjgpLjgIxpbnN0YWxsLnB5IOOBruWGjeOCs+ODlOODmuOAjeOBquOBl+OB'
        'p+WFqCBQQyDjgavphY3jgozjgosgKD0g5YaN6YWN5biD5LiN6KaBKeOAggogICAgICAqIGNvbmZp'
        'Zy5qc29uIOOBr+inpuOCieOBquOBhCAodG9rZW4g44KS5L+d5oyBKeOAggogICAgICAqIOWjiuOC'
        'jOOBn+eJiOOBp+ipsOOCgOOBruOCkumYsuOBkOOBn+OCgeOAgeWPluOCiui+vOOCgOWJjeOBqyBj'
        'b21waWxlIOaknOiovCArIOaXouWtmOOCkiAuYmFrIOOBq+mAgOmBv+OAggogICAgIiIiCiAgICBz'
        'cmNfZGlyID0gb3MucGF0aC5qb2luKF9saXZlX3BhdGgoY2FjaGUpLCAiX2Jvb3RzdHJhcCIpCiAg'
        'ICBzcmNfdXBkYXRlciA9IG9zLnBhdGguam9pbihzcmNfZGlyLCAibWF5YXRvb2xzX3VwZGF0ZXIu'
        'cHkiKQogICAgaWYgbm90IG9zLnBhdGguaXNmaWxlKHNyY191cGRhdGVyKToKICAgICAgICByZXR1'
        'cm4KICAgIGJ1bmRsZWQgPSBfcGFyc2VfYm9vdHN0cmFwX3ZlcnNpb24oc3JjX3VwZGF0ZXIpCiAg'
        'ICBpZiBidW5kbGVkIGlzIE5vbmUgb3IgYnVuZGxlZCA8PSBCT09UU1RSQVBfVkVSU0lPTjoKICAg'
        'ICAgICByZXR1cm4KICAgIHRyeToKICAgICAgICB3aXRoIG9wZW4oc3JjX3VwZGF0ZXIsICJyIiwg'
        'ZW5jb2Rpbmc9InV0Zi04IikgYXMgZjoKICAgICAgICAgICAgY29tcGlsZShmLnJlYWQoKSwgc3Jj'
        'X3VwZGF0ZXIsICJleGVjIikgICAjIOWjiuOCjOOBnyB1cGRhdGVyIOOCkuWPluOCiui+vOOBvuOB'
        'quOBhOS/nemZugogICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICBfbG9nKCJib290c3RyYXAg'
        '6Ieq5bex5pu05paw44KS6KaL6YCB44KKICjmlrAgdXBkYXRlciDjgYwgY29tcGlsZSDkuI3lj68p'
        'OiB2JXMiICUgYnVuZGxlZCkKICAgICAgICByZXR1cm4KICAgIGRzdF9kaXIgPSBvcy5wYXRoLmpv'
        'aW4oY2FjaGUsICJib290c3RyYXAiKQogICAgb3MubWFrZWRpcnMoZHN0X2RpciwgZXhpc3Rfb2s9'
        'VHJ1ZSkKICAgIGZvciBuYW1lIGluICgibWF5YXRvb2xzX3VwZGF0ZXIucHkiLCAidXNlclNldHVw'
        'LnB5Iik6CiAgICAgICAgc3AgPSBvcy5wYXRoLmpvaW4oc3JjX2RpciwgbmFtZSkKICAgICAgICBp'
        'ZiBub3Qgb3MucGF0aC5pc2ZpbGUoc3ApOgogICAgICAgICAgICBjb250aW51ZQogICAgICAgIGRw'
        'ID0gb3MucGF0aC5qb2luKGRzdF9kaXIsIG5hbWUpCiAgICAgICAgdHJ5OgogICAgICAgICAgICBp'
        'ZiBvcy5wYXRoLmlzZmlsZShkcCk6CiAgICAgICAgICAgICAgICBzaHV0aWwuY29weTIoZHAsIGRw'
        'ICsgIi5iYWsiKQogICAgICAgICAgICBzaHV0aWwuY29weTIoc3AsIGRwKQogICAgICAgIGV4Y2Vw'
        'dCBFeGNlcHRpb246CiAgICAgICAgICAgIF9sb2coImJvb3RzdHJhcCDoh6rlt7Hmm7TmlrDjgafj'
        'grPjg5Tjg7zlpLHmlZcgKCVzKTpcbiVzIiAlIChuYW1lLCB0cmFjZWJhY2suZm9ybWF0X2V4Yygp'
        'KSkKICAgICAgICAgICAgcmV0dXJuCiAgICBfbG9nKCJ1cGRhdGVyIOOCkuiHquW3seabtOaWsOOB'
        'l+OBvuOBl+OBnyAodiVzIC0+IHYlcynjgILmrKHlm54gTWF5YSDotbfli5Xjgaflj43mmKDjgZXj'
        'gozjgb7jgZnjgIIiCiAgICAgICAgICUgKEJPT1RTVFJBUF9WRVJTSU9OLCBidW5kbGVkKSkKCgoj'
        'IC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLQojIOWPluW+lyAoYmFja2dyb3VuZCB0aHJlYWTjgIJNYXlhIEFQ'
        'SSDjga/op6bjgonjgarjgYQpCiMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tCmRlZiBjaGVja19hbmRfZG93'
        'bmxvYWQoY2ZnOiBkaWN0LCBjYWNoZTogc3RyKSAtPiBOb25lOgogICAgcmVtb3RlID0gX3Jlc29s'
        'dmVfcmVtb3RlKGNmZykKICAgIHZlcnNpb24gPSByZW1vdGVbInZlcnNpb24iXQogICAgc3RhdGUg'
        'PSBfcmVhZF9zdGF0ZShjYWNoZSkKICAgIGxpdmUgPSBfbGl2ZV9wYXRoKGNhY2hlKQogICAgbGl2'
        'ZV9vayA9IF9pc19saW5rKGxpdmUpIGFuZCBfaXNfdmFsaWRfcGF5bG9hZChsaXZlKQoKICAgIGlm'
        'IGxpdmVfb2sgYW5kIHN0YXRlLmdldCgiYWN0aXZlIikgPT0gdmVyc2lvbiBhbmQgbm90IHN0YXRl'
        'LmdldCgicGVuZGluZyIpOgogICAgICAgIF9sb2coIuacgOaWsOOBp+OBmSAoJXMpIiAlIHZlcnNp'
        'b25bOjE2XSkKICAgICAgICByZXR1cm4KCiAgICB2cCA9IF92ZXJzaW9uX3BhdGgoY2FjaGUsIHZl'
        'cnNpb24pCiAgICBpZiBub3QgX2lzX3ZhbGlkX3BheWxvYWQodnApOgogICAgICAgIF9sb2coIuaW'
        'sOODkOODvOOCuOODp+ODs+OCkuWPluW+l+OBl+OBvuOBmTogJXMiICUgdmVyc2lvbls6MTZdKQog'
        'ICAgICAgIHRtcCA9IG9zLnBhdGguam9pbihjYWNoZSwgInRtcCIpCiAgICAgICAgc2h1dGlsLnJt'
        'dHJlZShfbHAodG1wKSwgaWdub3JlX2Vycm9ycz1UcnVlKQogICAgICAgIG9zLm1ha2VkaXJzKF9s'
        'cCh0bXApLCBleGlzdF9vaz1UcnVlKQogICAgICAgIHppcHBhdGggPSBvcy5wYXRoLmpvaW4odG1w'
        'LCAiZG93bmxvYWQuemlwIikKICAgICAgICBfZG93bmxvYWQocmVtb3RlWyJ1cmwiXSwgemlwcGF0'
        'aCwgY2ZnLmdldCgidG9rZW4iLCAiIiksIHJlbW90ZS5nZXQoImFjY2VwdCIsIEFDQ0VQVF9BUkNI'
        'SVZFKSkKICAgICAgICB3aXRoIHppcGZpbGUuWmlwRmlsZSh6aXBwYXRoKSBhcyB6OgogICAgICAg'
        'ICAgICBpZiB6LnRlc3R6aXAoKSBpcyBub3QgTm9uZToKICAgICAgICAgICAgICAgIHJhaXNlIFJ1'
        'bnRpbWVFcnJvcigiemlwIOegtOaQjSIpCiAgICAgICAgICAgIGV4ID0gb3MucGF0aC5qb2luKHRt'
        'cCwgImV4IikKICAgICAgICAgICAgb3MubWFrZWRpcnMoX2xwKGV4KSwgZXhpc3Rfb2s9VHJ1ZSkK'
        'ICAgICAgICAgICAgei5leHRyYWN0YWxsKF9scChleCkpCiAgICAgICAgcm9vdCA9IF9mbGF0dGVu'
        'X3NpbmdsZV90b3AoZXgpCiAgICAgICAgaWYgbm90IF9pc192YWxpZF9wYXlsb2FkKHJvb3QpOgog'
        'ICAgICAgICAgICByYWlzZSBSdW50aW1lRXJyb3IoIuWPluW+l+eJqeOBqyAlcyDjgYzopovjgaTj'
        'gYvjgorjgb7jgZvjgpMiICUgU0VOVElORUwpCiAgICAgICAgb3MubWFrZWRpcnMoX2xwKF92ZXJz'
        'aW9uc19kaXIoY2FjaGUpKSwgZXhpc3Rfb2s9VHJ1ZSkKICAgICAgICBzaHV0aWwucm10cmVlKF9s'
        'cCh2cCksIGlnbm9yZV9lcnJvcnM9VHJ1ZSkKICAgICAgICBzaHV0aWwubW92ZShfbHAocm9vdCks'
        'IF9scCh2cCkpCiAgICAgICAgc2h1dGlsLnJtdHJlZShfbHAodG1wKSwgaWdub3JlX2Vycm9ycz1U'
        'cnVlKQogICAgICAgIF9sb2coIuWPluW+l+WujOS6hjogJXMiICUgdmVyc2lvbls6MTZdKQoKICAg'
        'ICMg5qyh5Zue6LW35YuV44Gn5Y+N5pigIChwZW5kaW5nIOOBq+epjeOCgCnjgILjgZ/jgaDjgZcg'
        'bGl2ZSDjgYznhKHjgZHjgozjgbDljbPpgannlKggKOWIneWbninjgIIKICAgIHN0YXRlWyJwZW5k'
        'aW5nIl0gPSB2ZXJzaW9uCiAgICBfd3JpdGVfc3RhdGUoY2FjaGUsIHN0YXRlKQogICAgaWYgbm90'
        'IGxpdmVfb2s6CiAgICAgICAgYXBwbHlfcGVuZGluZyhjYWNoZSkKICAgIGVsc2U6CiAgICAgICAg'
        'X2xvZygi5qyh5ZueIE1heWEg6LW35YuV44Gn5Y+N5pig44GV44KM44G+44GZOiAlcyIgJSB2ZXJz'
        'aW9uWzoxNl0pCgoKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KIyDjgqjjg7Pjg4jjg6rjg53jgqTjg7Pj'
        'g4gKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0t'
        'LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KZGVmIHJ1bihjb25maWdfcGF0aDogc3RyIHwgTm9uZSA9'
        'IE5vbmUsIGJsb2NraW5nOiBib29sID0gRmFsc2UpIC0+IE5vbmU6CiAgICBnbG9iYWwgX0xPR19D'
        'QUNIRQogICAgdHJ5OgogICAgICAgIGNmZyA9IGxvYWRfY29uZmlnKGNvbmZpZ19wYXRoKQogICAg'
        'ZXhjZXB0IEV4Y2VwdGlvbiBhcyBlOgogICAgICAgIF9sb2coImNvbmZpZy5qc29uIOiqrei+vOWk'
        'seaVlyAo5pyq6YWN572uPyk6ICVzIiAlIGUpCiAgICAgICAgcmV0dXJuCgogICAgcmF3ID0gY2Zn'
        'LmdldCgiY2FjaGVfZGlyIikKICAgIGNhY2hlID0gb3MucGF0aC5leHBhbmR2YXJzKG9zLnBhdGgu'
        'ZXhwYW5kdXNlcihyYXcpKSBpZiByYXcgZWxzZSBkZWZhdWx0X2NhY2hlX2RpcigpCiAgICBfTE9H'
        'X0NBQ0hFID0gY2FjaGUKICAgIHRyeToKICAgICAgICBvcy5tYWtlZGlycyhfdmVyc2lvbnNfZGly'
        'KGNhY2hlKSwgZXhpc3Rfb2s9VHJ1ZSkKICAgIGV4Y2VwdCBFeGNlcHRpb246CiAgICAgICAgX2xv'
        'Zygi44Kt44Oj44OD44K344Ol5L2c5oiQ5aSx5pWXOlxuIiArIHRyYWNlYmFjay5mb3JtYXRfZXhj'
        'KCkpCiAgICAgICAgcmV0dXJuCgogICAgIyDotbfli5Xjg4jjg6zjg7zjgrk6IHJ1bigpIOOBjOWR'
        'vOOBsOOCjOOBn+S6i+Wun+OBqOWIneacn+eKtuaFi+OCkuavjuWbniAxIOihjOaui+OBmeOAggog'
        'ICAgIyAgIOi1t+WLleOBruOBn+OBs+OBqyB1cGRhdGVyIOOBjOWun+mam+OBq+i1sOOBo+OBn+OB'
        'iyAvIHRva2Vu44O7YXV0aOODu2xpdmUg44KS44Gp44GG6KaL44Gm44GE44KL44GL44KSCiAgICAj'
        'ICAgdXBkYXRlLmxvZyDjgafov73jgYjjgovjgojjgYbjgavjgZnjgosgKOOAjOWGjei1t+WLleOB'
        'l+OBn+OBruOBq+a2iOOBiOOBquOBhOOAjeOBruWIh+OCiuWIhuOBkeeUqCnjgIIKICAgIHRyeToK'
        'ICAgICAgICBzdDAgPSBfcmVhZF9zdGF0ZShjYWNoZSkKICAgICAgICBsdiA9IF9saXZlX3BhdGgo'
        'Y2FjaGUpCiAgICAgICAgX2xvZygi6LW35YuV44OB44Kn44OD44KvOiB1cGRhdGVyIHYlcyAvIHRv'
        'a2VuPSVzIC8gYXV0aD0lcyAvIGxpdmU9JXMgLyBhY3RpdmU9JXMgLyBibG9ja2luZz0lcyIKICAg'
        'ICAgICAgICAgICUgKEJPT1RTVFJBUF9WRVJTSU9OLAogICAgICAgICAgICAgICAgIuaciSIgaWYg'
        'KGNmZy5nZXQoInRva2VuIikgb3IgIiIpLnN0cmlwKCkgZWxzZSAi54ShIiwKICAgICAgICAgICAg'
        'ICAgIHN0MC5nZXQoImF1dGgiLCAi5pyqIiksCiAgICAgICAgICAgICAgICAi5pyJIiBpZiAoX2lz'
        'X2xpbmsobHYpIGFuZCBfaXNfdmFsaWRfcGF5bG9hZChsdikpIGVsc2UgIueEoSIsCiAgICAgICAg'
        'ICAgICAgICBzdHIoc3QwLmdldCgiYWN0aXZlIikgb3IgIi0iKVs6MTZdLCBib29sKGJsb2NraW5n'
        'KSkpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHBhc3MKCiAgICAjIDApIHRva2VuIOiq'
        'jeiovOOCsuODvOODiDogdG9rZW4g44GM54Sh44GR44KM44Gw44OE44O844OrIChsaXZlKSDjgpLl'
        'pJbjgZfjgabntYLkuoYgPSDjg4Tjg7zjg6vjgpLoqq3jgb/ovrzjgb7jgZvjgarjgYTjgIIKICAg'
        'IGlmIG5vdCBjZmcuZ2V0KCJ0b2tlbiIpOgogICAgICAgIHRyeToKICAgICAgICAgICAgX3NldF90'
        'b29sc19lbmFibGVkKGNhY2hlLCBGYWxzZSkKICAgICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAg'
        'ICAgICAgICBfbG9nKCLjg4Tjg7zjg6vnhKHlirnljJbjgafkvovlpJY6XG4iICsgdHJhY2ViYWNr'
        'LmZvcm1hdF9leGMoKSkKICAgICAgICBfbG9nKCJ0b2tlbiDmnKroqK3lrpo6IOODhOODvOODq+OC'
        'kuiqreOBv+i+vOOBv+OBvuOBm+OCkyAobGl2ZSDjgpLlpJbjgZfjgb7jgZfjgZ8p44CCdG9rZW4g'
        '44KS6Kit5a6a44GX44GmIE1heWEg44KS5YaN6LW35YuV44GX44Gm44GP44Gg44GV44GE44CCIikK'
        'ICAgICAgICByZXR1cm4KCiAgICAjIDAuNSkg5YmN5Zue44Gu6KqN6Ki857WQ5p6c44KS5ZCM5pyf'
        '44Gn5Y+N5pig44CCImZhaWwiICjliY3lm54gNDAxKSDjgarjgokgKirjg4Tjg7zjg6vjgpLnhKHl'
        'irnljJbjgZfjgZ/jgb7jgb7jgIEKICAgICMgICAgICBhcHBseV9wZW5kaW5nIC8g5YaN44Oq44Oz'
        '44KvIC8gc2VsZi11cGRhdGUg44KSIHNraXAqKiDjgZnjgovjgILjgZPjgozjgYznhKHjgYTjgagg'
        'YXBwbHlfcGVuZGluZyDjgoQKICAgICMgICAgICBjaGVja19hbmRfZG93bmxvYWQg44Gu5YaN44Oq'
        '44Oz44Kv44GM54Sh5Yq5IHRva2VuIOOBp+OCgiBsaXZlIOOCkuS9nOOCiuebtOOBl+OBpuOBl+OB'
        'vuOBhiAo5a6f5qmf44Gn55m655SfKeOAggogICAgIyAgICAgIHRva2VuIOOBjOebtOOBo+OBpuOB'
        'hOOCjOOBsOS4i+OBriB3b3JrZXIg44GMIGNoZWNrIOaIkOWKn+aZguOBq+WGjeeiuuiqjeOBl+OB'
        'puW+qeW4sOOBleOBm+OCi+OAggogICAgaWYgX3JlYWRfc3RhdGUoY2FjaGUpLmdldCgiYXV0aCIp'
        'ID09ICJmYWlsIjoKICAgICAgICB0cnk6CiAgICAgICAgICAgIF9zZXRfdG9vbHNfZW5hYmxlZChj'
        'YWNoZSwgRmFsc2UpCiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICAgICAgX2xvZygi'
        '44OE44O844Or54Sh5Yq55YyW44Gn5L6L5aSWOlxuIiArIHRyYWNlYmFjay5mb3JtYXRfZXhjKCkp'
        'CiAgICAgICAgX2xvZygi5YmN5ZueIHRva2VuIOiqjeiovOOBq+WkseaVl+OBl+OBpuOBhOOBvuOB'
        'mTog44OE44O844Or44Gv54Sh5Yq544Gn44GZICjmnInlirnjgaogdG9rZW4g44Gr55u044GX44Gm'
        '5YaN6LW35YuV44Gn5b6p5biwKeOAgiIpCiAgICBlbHNlOgogICAgICAgICMgMSkgcGVuZGluZyDj'
        'gpIgbGl2ZSDjgavpgannlKggKOiqjeiovCBPSyAvIOacqueiuuiqjeOBruOBqOOBjeOBruOBv+OA'
        'gmp1bmN0aW9uIOiyvOabv+OBquOBruOBpyBsb2NrZWQg44Gn44KC5oiQ5YqfKQogICAgICAgIHRy'
        'eToKICAgICAgICAgICAgYXBwbHlfcGVuZGluZyhjYWNoZSkKICAgICAgICBleGNlcHQgRXhjZXB0'
        'aW9uOgogICAgICAgICAgICBfbG9nKCJhcHBseV9wZW5kaW5nIOOBp+S+i+WkljpcbiIgKyB0cmFj'
        'ZWJhY2suZm9ybWF0X2V4YygpKQogICAgICAgICMgMS41KSBsaXZlIOOBq+WQjOaiseOBleOCjOOB'
        'n+aWsOOBl+OBhCBib290c3RyYXAg44GnIHVwZGF0ZXIg44KS6Ieq5bex5pu05pawIChpbnN0YWxs'
        'LnB5IOWGjemFjeW4g+S4jeimgeWMlikKICAgICAgICB0cnk6CiAgICAgICAgICAgIF9yZWZyZXNo'
        'X2Jvb3RzdHJhcChjYWNoZSkKICAgICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgICAgICBf'
        'bG9nKCJib290c3RyYXAg6Ieq5bex5pu05paw44Gn5L6L5aSWOlxuIiArIHRyYWNlYmFjay5mb3Jt'
        'YXRfZXhjKCkpCiAgICAgICAgIyAyKSDlj6TjgYTniYjjg5Xjgqnjg6vjg4DjgpLmjoPpmaQgKGFj'
        'dGl2ZS9wZW5kaW5nIOOBr+aui+OBmSkKICAgICAgICB0cnk6CiAgICAgICAgICAgIHN0ID0gX3Jl'
        'YWRfc3RhdGUoY2FjaGUpCiAgICAgICAgICAgIF9jbGVhbnVwX3ZlcnNpb25zKGNhY2hlLCBhbHdh'
        'eXNfa2VlcD0oc3QuZ2V0KCJhY3RpdmUiKSwgc3QuZ2V0KCJwZW5kaW5nIikpKQogICAgICAgIGV4'
        'Y2VwdCBFeGNlcHRpb246CiAgICAgICAgICAgIHBhc3MKCiAgICBpZiBub3QgY2ZnLmdldCgiZW5h'
        'YmxlZCIsIFRydWUpOgogICAgICAgIF9sb2coIuiHquWLleabtOaWsOOBr+eEoeWKueWMluOBleOC'
        'jOOBpuOBhOOBvuOBmSAoY29uZmlnLmVuYWJsZWQ9ZmFsc2UpIikKICAgICAgICByZXR1cm4KCiAg'
        'ICAjIHRva2VuIOacieWKueaAp+OBryAqKuavjui1t+WLleOBp+W/heOBmueiuuiqjeOBmeOCiyoq'
        'IChyZXZva2Ug44KS5qyh5Zue6LW35YuV44Gn56K65a6f44Gr5qSc5Ye6ID0g44Kt44Or44K544Kk'
        '44OD44OBKeOAggogICAgIyBjaGVja19pbnRlcnZhbF9ob3VycyDjga8gKirmm7TmlrAgREwg44Gu'
        '44G/Kiog44KSIHRocm90dGxlIOOBmeOCi+OAguaXp+Wun+ijheOBryB0b2tlbiDnorroqo3jgZTj'
        'gagKICAgICMgaW50ZXJ2YWwg44K544Kt44OD44OX44GX44Gm44GE44Gf44Gf44KB44CB6ZaT6ZqU'
        '5YaF44GvIHJldm9rZSDjgZfjgabjgoLnhKHlirnljJbjgZXjgozjgarjgYvjgaPjgZ8gKOOCu+OC'
        'reODpeODquODhuOCo+eptCnjgIIKICAgIGludGVydmFsID0gZmxvYXQoY2ZnLmdldCgiY2hlY2tf'
        'aW50ZXJ2YWxfaG91cnMiLCAwKSBvciAwKSAqIDM2MDAuMAogICAgc3RhdGUgPSBfcmVhZF9zdGF0'
        'ZShjYWNoZSkKICAgIGR1ZSA9IG5vdCAoaW50ZXJ2YWwgPiAwIGFuZCAodGltZS50aW1lKCkgLSBm'
        'bG9hdChzdGF0ZS5nZXQoImxhc3RfY2hlY2siLCAwKSkpIDwgaW50ZXJ2YWwpCgogICAgZGVmIHdv'
        'cmtlcigpOgogICAgICAgIHRyeToKICAgICAgICAgICAgaWYgZHVlOgogICAgICAgICAgICAgICAg'
        'Y2hlY2tfYW5kX2Rvd25sb2FkKGNmZywgY2FjaGUpICAgIyDniYjnorroqo0gKyDlv4XopoHjgarj'
        'gokgREwgKGxhc3RfY2hlY2sg44GvIGZpbmFsbHkg44Gn5pu05pawKQogICAgICAgICAgICBlbHNl'
        'OgogICAgICAgICAgICAgICAgIyDplpPpmpTlhoU6IERMIOOBr+OBm+OBmiB0b2tlbiDmnInlirnm'
        'gKfjgaDjgZHnorroqo0gKDQwMSDjgarjgonjgZPjgZPjgafmipXjgZLjgosg4oaSIOS4i+OBp+eE'
        'oeWKueWMlikKICAgICAgICAgICAgICAgIF9yZXNvbHZlX3JlbW90ZShjZmcpCiAgICAgICAgICAg'
        'ICAgICBfbG9nKCLjg4Hjgqfjg4Pjgq/plpPpmpTlhoU6IHRva2VuIOacieWKueaAp+OBruOBv+ei'
        'uuiqjSAo5pu05pawIERMIOOBryBza2lwKSIpCiAgICAgICAgICAgICMg6KqN6Ki8IE9LIChHaXRI'
        'dWIg44Gr5bGK44GE44GfKSDihpIg57WQ5p6c44KS5L+d5a2Y44GX44OE44O844Or44KS5pyJ5Yq5'
        '5YyWICjnhKHlirnnirbmhYvjgYvjgonjga7lvqnluLDjgpLlkKvjgoApCiAgICAgICAgICAgIF9t'
        'YXJrX2F1dGgoY2FjaGUsICJvayIpCiAgICAgICAgICAgIHRyeToKICAgICAgICAgICAgICAgIF9z'
        'ZXRfdG9vbHNfZW5hYmxlZChjYWNoZSwgVHJ1ZSkKICAgICAgICAgICAgZXhjZXB0IEV4Y2VwdGlv'
        'bjoKICAgICAgICAgICAgICAgIF9sb2coIuODhOODvOODq+acieWKueWMluOBp+S+i+WkljpcbiIg'
        'KyB0cmFjZWJhY2suZm9ybWF0X2V4YygpKQogICAgICAgIGV4Y2VwdCB1cmxsaWIuZXJyb3IuSFRU'
        'UEVycm9yIGFzIGU6CiAgICAgICAgICAgIGlmIGUuY29kZSA9PSA0MDE6CiAgICAgICAgICAgICAg'
        'ICAjIOeEoeWKuSAvIOWkseWKuSAvIHJldm9rZSDjgZXjgozjgZ8gdG9rZW4gPSDoqo3oqLzjgarj'
        'gZcg4oaSIOiomOmMsuOBl+OBpuODhOODvOODq+OCkueEoeWKueWMlgogICAgICAgICAgICAgICAg'
        'X21hcmtfYXV0aChjYWNoZSwgImZhaWwiKQogICAgICAgICAgICAgICAgdHJ5OgogICAgICAgICAg'
        'ICAgICAgICAgIF9zZXRfdG9vbHNfZW5hYmxlZChjYWNoZSwgRmFsc2UpCiAgICAgICAgICAgICAg'
        'ICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgICAgICAgICAgICAgIHBhc3MKICAgICAgICAgICAg'
        'ICAgIF9sb2coInRva2VuIOiqjeiovOWkseaVlyAoNDAxIEJhZCBjcmVkZW50aWFscyk6IOODhOOD'
        'vOODq+OCkueEoeWKueWMluOBl+OBvuOBl+OBn+OAgiIKICAgICAgICAgICAgICAgICAgICAgIuac'
        'ieWKueOBqiB0b2tlbiDjgavlt67jgZfmm7/jgYjjgaYgTWF5YSDjgpLlho3otbfli5XjgZfjgabj'
        'gY/jgaDjgZXjgYTjgIIiKQogICAgICAgICAgICBlbHNlOgogICAgICAgICAgICAgICAgIyA0MDEg'
        '5Lul5aSWIChyYXRlLWxpbWl0L+aoqemZkC/kuIDmmYLpmpzlrrMpIOOBr+eEoeWKueWMluOBl+OB'
        'quOBhCAo6Kqk6YGu5pat44KS6YG/44GR44KLKQogICAgICAgICAgICAgICAgdHJ5OgogICAgICAg'
        'ICAgICAgICAgICAgIGJvZHkgPSBlLnJlYWQoKS5kZWNvZGUoInV0Zi04IiwgInJlcGxhY2UiKS5z'
        'dHJpcCgpWzozMDBdCiAgICAgICAgICAgICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgICAg'
        'ICAgICAgICAgIGJvZHkgPSAiIgogICAgICAgICAgICAgICAgX2xvZygi5pu05paw44OB44Kn44OD'
        '44Kv5aSx5pWXIChIVFRQICVzICVzKS4gJXMlcyIKICAgICAgICAgICAgICAgICAgICAgJSAoZS5j'
        'b2RlLCBlLnJlYXNvbiwgX2h0dHBfaGludChlLmNvZGUpLCAoIlxuICBHaXRIdWI6ICIgKyBib2R5'
        'KSBpZiBib2R5IGVsc2UgIiIpKQogICAgICAgIGV4Y2VwdCBFeGNlcHRpb246CiAgICAgICAgICAg'
        'ICMg44ON44OD44OI44Ov44O844Kv6Zqc5a6z562J44Gv54Sh5Yq55YyW44GX44Gq44GEICjjgqrj'
        'g5Xjg6njgqTjg7PlronlhagpCiAgICAgICAgICAgIF9sb2coIuabtOaWsOODgeOCp+ODg+OCr+Wk'
        'seaVlzpcbiIgKyB0cmFjZWJhY2suZm9ybWF0X2V4YygpKQogICAgICAgIGZpbmFsbHk6CiAgICAg'
        'ICAgICAgICMgbGFzdF9jaGVjayDjga/jgIzniYjjgpLnorroqo3jgZfjgZ/mmYLjgI3jgaDjgZHl'
        'iY3pgLLjgZXjgZvjgovjgIJwcm9iZSDjga7jgb8gKOmWk+malOWGhSkg44Gu5pmC44GrCiAgICAg'
        'ICAgICAgICMg5pu05paw44GZ44KL44GoIERMIOODgeOCp+ODg+OCr+OBjOawuOS5heOBq+WFiOmA'
        'geOCiuOBleOCjOOCi+OBruOBp+inpuOCieOBquOBhOOAggogICAgICAgICAgICBpZiBkdWU6CiAg'
        'ICAgICAgICAgICAgICBzdDIgPSBfcmVhZF9zdGF0ZShjYWNoZSkKICAgICAgICAgICAgICAgIHN0'
        'MlsibGFzdF9jaGVjayJdID0gdGltZS50aW1lKCkKICAgICAgICAgICAgICAgIF93cml0ZV9zdGF0'
        'ZShjYWNoZSwgc3QyKQoKICAgIGlmIGJsb2NraW5nOgogICAgICAgIHdvcmtlcigpCiAgICBlbHNl'
        'OgogICAgICAgIHRocmVhZGluZy5UaHJlYWQodGFyZ2V0PXdvcmtlciwgbmFtZT0iTWF5YVRvb2xz'
        'VXBkYXRlciIsIGRhZW1vbj1UcnVlKS5zdGFydCgpCg=='
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
