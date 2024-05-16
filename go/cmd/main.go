package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

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
	allLegIkMotions := usecase.ConvertLegIk(allRotateMotions, nil, modelPath, 100000)

	mlog.I("Fix Ground Motion ================")
	allGroundMotions := usecase.FixGround(allLegIkMotions, modelPath)

	mlog.I("Fix Heel Motion ================")
	allHeelMotions := usecase.FixHeel(allFrames, allGroundMotions, modelPath)

	mlog.I("Convert Arm Ik Motion ================")
	allArmIkMotions := usecase.ConvertArmIk(allHeelMotions, nil, modelPath, 100000)

	// モーションを出力する
	{
		for i, motion := range allArmIkMotions {
			mlog.I("Output Full Motion [%d/%d] ...", i, len(allArmIkMotions))

			motionName := fmt.Sprintf("%02d_full.vmd", i+1)
			motion.Path = filepath.Join(dirPath, motionName)
			err := vmd.Write(motion)
			if err != nil {
				mlog.E("Failed to write full vmd: %v", err)
			}
		}
	}

	mlog.I("Reduce Motion [narrow] ================")
	narrowReduceMotions := usecase.Reduce(allArmIkMotions, modelPath, 0.05, 0.00001, 0, "narrow")

	// モーションを出力する
	{
		for i, motion := range narrowReduceMotions {
			mlog.I("Output Narrow Reduce Motion [%d/%d] ...", i, len(narrowReduceMotions))

			motionName := fmt.Sprintf("%02d_reduce_narrow.vmd", i+1)
			motion.Path = filepath.Join(dirPath, motionName)
			err := vmd.Write(motion)
			if err != nil {
				mlog.E("Failed to write narrow reduce vmd: %v", err)
			}
		}
	}

	mlog.I("Reduce Motion [wide] ================")
	wideReduceMotions := usecase.Reduce(allArmIkMotions, modelPath, 0.07, 0.00005, 2, "wide")

	// モーションを出力する
	{
		for i, motion := range wideReduceMotions {
			mlog.I("Output Wide Reduce Motion [%d/%d] ...", i, len(wideReduceMotions))

			motionName := fmt.Sprintf("%02d_reduce_wide.vmd", i+1)
			motion.Path = filepath.Join(dirPath, motionName)
			err := vmd.Write(motion)
			if err != nil {
				mlog.E("Failed to write wide reduce vmd: %v", err)
			}
		}
	}

	// complete ファイルを出力する
	{
		completePath := filepath.Join(dirPath, "complete")
		mlog.I("Output Complete File %s", completePath)
		f, err := os.Create(completePath)
		if err != nil {
			mlog.E("Failed to create complete file: %v", err)
			return
		}
		defer f.Close()
	}

	mlog.I("Done!")

}
