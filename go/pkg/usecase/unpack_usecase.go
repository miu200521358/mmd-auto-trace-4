package usecase

import (
	"encoding/json"
	"os"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"
)

// Unpack jsonデータを読み込んで、構造体に展開する
func Unpack(json_path string) (*model.Frames, error) {
	// JSONデータを読み込んで展開
	file, err := os.Open(json_path)
	if err != nil {
		mlog.E("Failed to open file: %v", err)
		return nil, err
	}
	defer file.Close()

	frames := new(model.Frames)
	decoder := json.NewDecoder(file)
	err = decoder.Decode(frames)
	if err != nil {
		mlog.E("Failed to decode json: %v", err)
		return nil, err
	}

	return frames, nil
}
