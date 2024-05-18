package main

import (
	"flag"
	"os"
	"path/filepath"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/usecase"
	"github.com/miu200521358/mmd-auto-trace-4/pkg/utils"
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
	allMoveMotions := usecase.Move(allFrames)

	if mlog.IsDebug() {
		utils.WriteVmdMotions(allFrames, allMoveMotions, dirPath, "1_move", "Move")
	}

	mlog.I("Rotate Motion ================")
	allRotateMotions := usecase.Rotate(allMoveMotions, modelPath)

	if mlog.IsDebug() {
		utils.WriteVmdMotions(allFrames, allRotateMotions, dirPath, "2_rotate", "Rotate")
	}

	mlog.I("Convert Leg Ik Motion ================")
	allLegIkMotions := usecase.ConvertLegIk(allRotateMotions, modelPath)

	if mlog.IsDebug() {
		utils.WriteVmdMotions(allFrames, allLegIkMotions, dirPath, "3_leg_ik", "Leg Ik")
	}

	mlog.I("Fix Ground Motion ================")
	allGroundMotions := usecase.FixGround(allLegIkMotions, modelPath)

	if mlog.IsDebug() {
		utils.WriteVmdMotions(allFrames, allGroundMotions, dirPath, "4_ground", "Ground")
	}

	mlog.I("Fix Heel Motion ================")
	allHeelMotions := usecase.FixHeel(allFrames, allGroundMotions, modelPath)

	if mlog.IsDebug() {
		utils.WriteVmdMotions(allFrames, allHeelMotions, dirPath, "5_heel", "Heel")
	}

	mlog.I("Convert Arm Ik Motion ================")
	allArmIkMotions := usecase.ConvertArmIk(allHeelMotions, modelPath)

	utils.WriteVmdMotions(allFrames, allArmIkMotions, dirPath, "full", "Full")

	mlog.I("Reduce Motion [narrow] ================")
	narrowReduceMotions := usecase.Reduce(allArmIkMotions, modelPath, 0.05, 0.00001, 0, "narrow")

	utils.WriteVmdMotions(allFrames, narrowReduceMotions, dirPath, "reduce_narrow", "Narrow Reduce")

	mlog.I("Reduce Motion [wide] ================")
	wideReduceMotions := usecase.Reduce(allArmIkMotions, modelPath, 0.07, 0.00005, 2, "wide")

	utils.WriteVmdMotions(allFrames, wideReduceMotions, dirPath, "reduce_wide", "Wide Reduce")

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
