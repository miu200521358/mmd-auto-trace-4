package utils

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

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

func WriteVmdMotions(frames *model.Frames, motion *vmd.VmdMotion, dirPath, fileSuffix, logPrefix string, motionNum, allNum int) error {
	mlog.I("Output %s Motion [%d/%d] ...", logPrefix, motionNum, allNum)

	motion.Path = filepath.Join(dirPath, GetVmdName(frames, fileSuffix))
	motion.SetName("MMD Motion Auto Trace v4 Model")

	err := vmd.Write(motion)
	if err != nil {
		mlog.E("Failed to write %s vmd %d: %v", logPrefix, motionNum, err)
	}
	return nil
}

func GetVmdName(frames *model.Frames, fileSuffix string) string {
	return strings.Replace(filepath.Base(frames.Path), "smooth.json", fmt.Sprintf("%s.vmd", fileSuffix), -1)
}

func GetCompleteName(framePath string) string {
	return strings.Replace(filepath.Base(framePath), "smooth.json", "complete", -1)
}

func WriteComplete(dirPath, framePath string) {
	// complete ファイルを出力する
	completePath := filepath.Join(dirPath, GetCompleteName(framePath))
	mlog.I("Output Complete File %s", completePath)

	f, err := os.Create(completePath)
	if err != nil {
		mlog.E("Failed to create complete file: %v", err)
		return
	}
	defer f.Close()
}
