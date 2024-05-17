package utils

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/cheggaaa/pb/v3"
	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/vmd"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/model"
)

func GetVmdFilePaths(dirPath string, suffix string) ([]string, error) {
	var paths []string
	err := filepath.Walk(dirPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if path != dirPath && info.IsDir() {
			// 直下だけ参照
			return filepath.SkipDir
		}
		if !info.IsDir() && (strings.HasSuffix(info.Name(), fmt.Sprintf("%s.vmd", suffix))) {
			paths = append(paths, path)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return paths, nil
}

func ReadVmdFiles(allVmdPaths []string) ([]*vmd.VmdMotion, error) {
	allPrevMotions := make([]*vmd.VmdMotion, len(allVmdPaths))
	for i, vmdPath := range allVmdPaths {
		mlog.I("Read Vmd [%02d/%02d] %s", i+1, len(allVmdPaths), filepath.Base(vmdPath))
		vr := &vmd.VmdMotionReader{}
		motion, err := vr.ReadByFilepath(vmdPath)
		if err != nil {
			mlog.E("Failed to read vmd: %v", err)
			return nil, err
		}
		allPrevMotions[i] = motion.(*vmd.VmdMotion)
	}

	return allPrevMotions, nil
}

func NewProgressBar(total int) *pb.ProgressBar {
	// ShowElapsedTime, ShowTimeLeft が経過時間と残り時間を表示するためのオプションです

	// プログレスバーのカスタムテンプレートを設定
	template := `{{ string . "prefix" }} {{counters . "%s/%s" "%s/?"}} {{bar . }} {{percent . "%.03f%%" "?"}} {{etime . "%s elapsed"}} {{rtime . "%s remain" "%s total" "???"}}`

	// プログレスバーの作成
	bar := pb.ProgressBarTemplate(template).Start(total)

	return bar
}

func WriteVmdMotions(allFrames []*model.Frames, motions []*vmd.VmdMotion, dirPath, fileSuffix, logPrefix string) error {
	errCh := make(chan error, len(motions))
	var wg sync.WaitGroup

	for i, frames := range allFrames {
		wg.Add(1)
		go func(i int, frames *model.Frames, motion *vmd.VmdMotion) {
			defer mlog.I("Output %s Motion [%d/%d] ...", logPrefix, i+1, len(motions))
			defer wg.Done()

			fileName := strings.Replace(filepath.Base(frames.Path), "smooth.json", fmt.Sprintf("%s.vmd", fileSuffix), -1)
			motion.Path = filepath.Join(dirPath, fileName)
			motion.SetName("MMD Motion Auto Trace v4 Model")

			err := vmd.Write(motion)
			if err != nil {
				mlog.E("Failed to write %s vmd: %v", logPrefix, err)
				errCh <- err
			}
		}(i, frames, motions[i])
	}

	wg.Wait()
	close(errCh)

	if len(errCh) > 0 {
		return <-errCh
	}

	return nil
}
