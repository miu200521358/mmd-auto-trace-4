package usecase

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/cheggaaa/pb/v3"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"
)

// Unpack jsonデータを読み込んで、構造体に展開する
func Unpack(dirPath string) ([]*model.Frames, error) {
	jsonPaths, err := getJSONFilePaths(dirPath)
	if err != nil {
		mlog.E("Failed to get json file paths: %v", err)
		return nil, err
	}

	allFrames := make([]*model.Frames, len(jsonPaths))

	// 全体のタスク数をカウント
	totalFrames := len(jsonPaths)
	bar := pb.StartNew(totalFrames)

	// Create a wait group to wait for all goroutines to finish
	var wg sync.WaitGroup

	// Iterate over the JSON file paths
	for i, json_path := range jsonPaths {
		// Increment the wait group counter
		wg.Add(1)

		// Launch a goroutine to process each JSON file
		go func(i int, path string) {
			// Decrement the wait group counter when the goroutine finishes
			defer wg.Done()
			defer bar.Increment()

			// JSONデータを読み込んで展開
			file, err := os.Open(path)
			if err != nil {
				mlog.E("[%s] Failed to open file: %v", path, err)
				return
			}
			defer file.Close()

			frames := new(model.Frames)
			frames.Path = path
			decoder := json.NewDecoder(file)
			err = decoder.Decode(frames)
			if err != nil {
				mlog.E("[%s] Failed to decode json: %v", path, err)
				return
			}

			// Send the frames to the result channel
			allFrames[i] = frames
		}(i, json_path)
	}

	wg.Wait()
	bar.Finish()

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
