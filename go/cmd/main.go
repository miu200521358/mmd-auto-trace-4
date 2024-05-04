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
