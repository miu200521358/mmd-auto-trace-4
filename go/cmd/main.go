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

	mlog.I("Unpack json ...")
	allFrames, err := usecase.Unpack(dirPath)
	if err != nil {
		mlog.E("Failed to unpack: %v", err)
		return
	}

	mlog.I("Move Motion ...")
	allMoveMotions, allMpMoveMotions := usecase.Move(allFrames)

	mlog.I("Rotate Motion ...")
	allRotateMotions := usecase.Rotate(allFrames, allMoveMotions, allMpMoveMotions, modelPath)

	mlog.I("Convert Leg Ik Motion ...")
	allLegIkMotions := usecase.ConvertLegIk(allRotateMotions, modelPath)

	mlog.I("Convert Arm Ik Motion ...")
	allArmIkMotions := usecase.ConvertArmIk(allLegIkMotions, modelPath)

	mlog.I("Fix Ground Motion ...")
	allGroundMotions := usecase.FixGround(allArmIkMotions, modelPath)

	mlog.I("Fix Heel Motion ...")
	allHeelMotions := usecase.FixHeel(allFrames, allGroundMotions, modelPath)

	mlog.I("Reduce Motion ...")
	allReductionMotions := usecase.Reduce(allHeelMotions, modelPath)

	for i, motion := range allHeelMotions {
		fileName := getResultFileName(filepath.Base(motion.Path))
		mlog.I("Output Vmd [%02d/%02d] %s", i+1, len(allHeelMotions), fileName)
		motion.Path = fmt.Sprintf("%s/%s", dirPath, fileName)
		err := vmd.Write(motion)
		if err != nil {
			mlog.E("Failed to write result vmd: %v", err)
		}
	}

	for i, motion := range allReductionMotions {
		fileName := getReduceFileName(filepath.Base(motion.Path))
		mlog.I("Output Vmd [%02d/%02d] %s", i+1, len(allReductionMotions), fileName)
		motion.Path = fmt.Sprintf("%s/%s", dirPath, fileName)
		err := vmd.Write(motion)
		if err != nil {
			mlog.E("Failed to write result vmd: %v", err)
		}
	}

	mlog.I("Done!")
}

func getResultFileName(fileName string) string {
	split := strings.Split(fileName, "_")
	if len(split) < 3 {
		return fileName
	}
	return split[1] + "_" + split[2] + "_result.vmd"
}

func getReduceFileName(fileName string) string {
	split := strings.Split(fileName, "_")
	if len(split) < 3 {
		return fileName
	}
	return split[1] + "_" + split[2] + "_result_reduce.vmd"
}
