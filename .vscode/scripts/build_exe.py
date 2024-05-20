import json
import os

# 環境変数 WORKSPACE_FOLDER の値を取得
workspace_folder = os.environ.get('WORKSPACE_FOLDER')

# 値を表示
print(f"workspace_folder: {workspace_folder}")

os.environ['GOOS'] = 'linux'
os.environ['GOARCH'] = 'amd64'

# Build command
# -o 出力フォルダ
# -trimpath ビルドパスを削除
# -v ビルドログを出力
# -a 全ての依存関係を再ビルド
# -buildmode=exe 実行可能ファイルを生成
# -ldflags "-s -w" バイナリサイズを小さくする
# -X main.logLevel=INFO ビルド時に変数を設定
# -gcflags "all=-N -l" デバッグ情報を削除
build_command = f"cd go && go build -o {workspace_folder}/build/mat4 " \
                f"-trimpath -v -a -buildmode=exe -ldflags \"-s -w -X main.logLevel=INFO\" " \
                f"{workspace_folder}/go/cmd/main.go"

print(f"build_command: {build_command}")

os.system(build_command)

# # -----------

# build_command = f"cd go && go build -o {workspace_folder}/build/mat42 " \
#                 f"-trimpath -v -a -buildmode=exe -ldflags \"-s -w -X main.logLevel=INFO\" " \
#                 f"{workspace_folder}/go/cmd2/main.go"

# print(f"build_command: {build_command}")

# os.system(build_command)

# Play beep sound
print("\a")
