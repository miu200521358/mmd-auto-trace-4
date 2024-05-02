package main

import (
	"os"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"

	"github.com/miu200521358/mmd-auto-trace-4/pkg/usecase"
)

var logLevel = "DEBUG"

func init() {
	switch logLevel {
	case "INFO":
		mlog.SetLevel(mlog.INFO)
	default:
		mlog.SetLevel(mlog.DEBUG)
	}
}

func main() {
	modelPath := os.Args[1]
	mlog.I("modelPath: %v", modelPath)

	dirPath := os.Args[2]
	mlog.I("dirPath: %v", dirPath)

	mlog.I("Unpack json ...")
	allFrames, err := usecase.Unpack(dirPath)
	if err != nil {
		mlog.E("Failed to unpack: %v", err)
		return
	}

	mlog.I("Move Motion ...")
	allMoveMotions := usecase.Move(allFrames)

	mlog.I("Rotate Motion ...")
	allRotateMotions := usecase.Rotate(allMoveMotions, modelPath)

	mlog.I("Convert Leg Ik Motion ...")
	allLegIkMotions := usecase.ConvertLegIk(allRotateMotions, modelPath)

	print(len(allLegIkMotions))
}
