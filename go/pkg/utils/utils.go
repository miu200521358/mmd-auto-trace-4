package utils

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/vmd"
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
