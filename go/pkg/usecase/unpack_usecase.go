package usecase

import (
	"encoding/json"
	"os"

	"github.com/miu200521358/mmd-auto-trace-4/go/pkg/model"

)

// Unpack jsonデータを読み込んで、構造体に展開する
func Unpack(json_path string) (*Frames, error) {
	// JSONデータを読み込んで展開

	file, err := os.Open(json_path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	frames := new(Frames)
	decoder := json.NewDecoder(file)
	err = decoder.Decode(frames)
	if err != nil {
		return nil, err
	}
}
