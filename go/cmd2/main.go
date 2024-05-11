package main

import (
	"flag"
	"os"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
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

	mlog.I("Unpack json ================")
	allFrames, err := usecase.Unpack(dirPath)
	if err != nil {
		mlog.E("Failed to unpack: %v", err)
		return
	}

	mlog.I("Move Motion ================")
	allMoveMotions, allMpMoveMotions := usecase.Move(allFrames)

	mlog.I("Rotate Motion ================")
	allRotateMotions := usecase.Rotate(allFrames, allMoveMotions, allMpMoveMotions, modelPath)

	mlog.I("Convert Leg Ik Motion ================")
	allLegIkMotions := usecase.ConvertLegIk(allRotateMotions, nil, modelPath)

	mlog.I("Fix Ground Motion ================")
	allGroundMotions := usecase.FixGround(allLegIkMotions, modelPath)

	mlog.I("Fix Heel Motion ================")
	allHeelMotions := usecase.FixHeel(allFrames, allGroundMotions, modelPath)

	mlog.I("Convert Arm Ik Motion ================")
	allArmIkMotions := usecase.ConvertArmIk(allHeelMotions, nil, modelPath)

	mlog.I("Reduce Motion [narrow] ================")
	usecase.Reduce(allArmIkMotions, modelPath, 0.05, 0.00001, 0, "narrow")

	mlog.I("Reduce Motion [wide] ================")
	usecase.Reduce(allArmIkMotions, modelPath, 0.07, 0.00005, 2, "wide")

	mlog.I("Done!")
}
