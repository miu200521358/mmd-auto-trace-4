package usecase

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"

)

// Unpack jsonデータを読み込んで、構造体に展開する
func Unpack(dir_path string) ([]*model.Frames, error) {
	var allFrames []*model.Frames

	json_paths, err := getJSONFilePaths(dir_path)
	if err != nil {
		mlog.E("Failed to get json file paths: %v", err)
		return nil, err
	}

	// Create a channel to receive the results
	resultCh := make(chan *model.Frames)

	// Create a wait group to wait for all goroutines to finish
	var wg sync.WaitGroup

	// Iterate over the JSON file paths
	for _, json_path := range json_paths {
		// Increment the wait group counter
		wg.Add(1)

		// Launch a goroutine to process each JSON file
		go func(path string) {
			// Decrement the wait group counter when the goroutine finishes
			defer wg.Done()

			// JSONデータを読み込んで展開
			file, err := os.Open(path)
			if err != nil {
				mlog.E("Failed to open file: %v", err)
				return
			}
			defer file.Close()

			frames := new(model.Frames)
			frames.Path = path
			decoder := json.NewDecoder(file)
			err = decoder.Decode(frames)
			if err != nil {
				mlog.E("Failed to decode json: %v", err)
				return
			}

			// Send the frames to the result channel
			resultCh <- frames
		}(json_path)
	}

	// Start a goroutine to close the result channel when all goroutines finish
	go func() {
		// Wait for all goroutines to finish
		wg.Wait()

		// Close the result channel
		close(resultCh)
	}()

	// Collect the results from the result channel
	for frames := range resultCh {
		allFrames = append(allFrames, frames)
	}

	return allFrames, nil
}

func getJSONFilePaths(dirPath string) ([]string, error) {
	var paths []string
	err := filepath.Walk(dirPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() && strings.HasSuffix(info.Name(), ".json") {
			paths = append(paths, path)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return paths, nil
}
