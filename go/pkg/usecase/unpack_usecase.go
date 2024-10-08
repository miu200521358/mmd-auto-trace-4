package usecase

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/utils"
)

// Unpack jsonデータを読み込んで、構造体に展開する
func Unpack(dirPath string) ([]*model.Frames, error) {
	mlog.I("Start: Unpack =============================")

	jsonPaths, err := getJSONFilePaths(dirPath)
	if err != nil {
		mlog.E("Failed to get json file paths: %v", err)
		return nil, err
	}

	allFrames := make([]*model.Frames, len(jsonPaths))

	// 全体のタスク数をカウント
	totalFrames := len(jsonPaths)
	bar := utils.NewProgressBar(totalFrames)

	for i, path := range jsonPaths {
		bar.Increment()
		mlog.I("[%d/%d] Unpack ...", i+1, len(jsonPaths))

		// JSONデータを読み込んで展開
		file, err := os.Open(path)
		if err != nil {
			mlog.E("[%s] Failed to open file: %v", path, err)
			break
		}
		defer file.Close()

		frames := new(model.Frames)
		frames.Path = path
		decoder := json.NewDecoder(file)
		err = decoder.Decode(frames)
		if err != nil {
			mlog.E("[%s] Failed to decode json: %v", path, err)
			break
		}

		// Send the frames to the result channel
		allFrames[i] = frames
	}

	bar.Finish()

	mlog.I("End: Unpack =============================")

	return allFrames, nil
}

func getJSONFilePaths(dirPath string) ([]string, error) {
	var paths []string
	err := filepath.Walk(dirPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if path != dirPath && info.IsDir() {
			// 直下だけ参照
			return filepath.SkipDir
		}
		if !info.IsDir() && (strings.HasSuffix(info.Name(), "_smooth.json")) {
			paths = append(paths, path)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return paths, nil
}
