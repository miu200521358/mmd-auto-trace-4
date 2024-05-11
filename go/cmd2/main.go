package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/vmd"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/usecase"
)

var logLevel string
var modelPath string
var dirPath string

func init() {
	flag.StringVar(&logLevel, "logLevel", "INFO", "set log level")
	flag.StringVar(&modelPath, "modelPath", "", "set model path")
	flag.StringVar(&dirPath, "dirPath", "", "set directory path")
	flag.Parse()

	switch logLevel {
	case "INFO":
		mlog.SetLevel(mlog.INFO)
	default:
		mlog.SetLevel(mlog.DEBUG)
	}
}

func main() {
	if modelPath == "" || dirPath == "" {
		mlog.E("modelPath and dirPath must be provided")
		os.Exit(1)
	}
	if modelPath == "" || dirPath == "" {
		mlog.E("modelPath and dirPath must be provided")
		os.Exit(1)
	}

	allVmdPaths, err := getResultVmdFilePaths(dirPath)
	if err != nil {
		mlog.E("Failed to get result vmd file paths: %v", err)
		return
	}
	allPrevMotions := make([]*vmd.VmdMotion, len(allVmdPaths))
	for i, vmdPath := range allVmdPaths {
		mlog.I("Read Vmd [%02d/%02d] %s", i+1, len(allVmdPaths), filepath.Base(vmdPath))
		vr := &vmd.VmdMotionReader{}
		motion, err := vr.ReadByFilepath(vmdPath)
		if err != nil {
			mlog.E("Failed to read vmd: %v", err)
			return
		}
		allPrevMotions[i] = motion.(*vmd.VmdMotion)
	}

	mlog.I("Reduce Motion [Narrow] ...")
	allNarrowReductionMotions := usecase.Reduce(allPrevMotions, modelPath, 0.05, 0.00001, 0, "narrow")

	for i, motion := range allNarrowReductionMotions {
		fileName := getResultFileName(filepath.Base(motion.Path), "narrow")
		mlog.I("Output Vmd [%02d/%02d] %s", i+1, len(allNarrowReductionMotions), fileName)
		motion.Path = fmt.Sprintf("%s/%s", dirPath, fileName)
		err := vmd.Write(motion)
		if err != nil {
			mlog.E("Failed to write result vmd: %v", err)
		}
	}

	mlog.I("Reduce Motion [Wide] ...")
	allWideReductionMotions := usecase.Reduce(allPrevMotions, modelPath, 0.07, 0.00005, 2, "wide")

	for i, motion := range allWideReductionMotions {
		fileName := getResultFileName(filepath.Base(motion.Path), "wide")
		mlog.I("Output Vmd [%02d/%02d] %s", i+1, len(allWideReductionMotions), fileName)
		motion.Path = fmt.Sprintf("%s/%s", dirPath, fileName)
		err := vmd.Write(motion)
		if err != nil {
			mlog.E("Failed to write result vmd: %v", err)
		}
	}

	mlog.I("Done!")
}

func getResultFileName(fileName string, suffix string) string {
	split := strings.Split(fileName, "_")
	if len(split) < 2 {
		return fileName
	}
	return split[0] + "_" + split[1] + "_result_reduce_" + suffix + ".vmd"
}

func getResultVmdFilePaths(dirPath string) ([]string, error) {
	var paths []string
	err := filepath.Walk(dirPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if path != dirPath && info.IsDir() {
			// 直下だけ参照
			return filepath.SkipDir
		}
		if !info.IsDir() && (strings.HasSuffix(info.Name(), "_result.vmd")) {
			paths = append(paths, path)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return paths, nil
}
