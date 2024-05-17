package main

import (
	"flag"
	"os"
	"path/filepath"

	"github.com/miu200521358/mlib_go/pkg/mutils/mlog"
	"github.com/miu200521358/mlib_go/pkg/vmd"

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

	// ----------------------------------------

	mlog.I("Unpack json ================")
	allFrames, err := usecase.Unpack(dirPath)
	if err != nil {
		mlog.E("Failed to unpack: %v", err)
		return
	}

	// 処理の後ろから順に読んでいって、1つ処理が終わったら終了
	// 全てのトレース作業完了したら、complete ファイルを出力する

	armIkMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_full")
	if err != nil {
		mlog.E("Failed to get arm ik vmd file paths: %v", err)
		return
	}

	var allArmIkMotions []*vmd.VmdMotion
	if armIkMotionPaths != nil {
		// 間引き --------
		mlog.I("Read Arm Ik Motion ================")
		allArmIkMotions, err = utils.ReadVmdFiles(armIkMotionPaths)
		if err != nil {
			mlog.E("Failed to read arm ik motion: %v", err)
			return
		}

		if allArmIkMotions != nil {

			mlog.I("Reduce Motion [narrow] ================")
			narrowReduceMotions := usecase.Reduce(allArmIkMotions, modelPath, 0.05, 0.00001, 0, "narrow")

			// モーションを出力する
			utils.WriteVmdMotions(allFrames, narrowReduceMotions, dirPath, "reduce_narrow", "Narrow Reduce")

			mlog.I("Reduce Motion [wide] ================")
			wideReduceMotions := usecase.Reduce(allArmIkMotions, modelPath, 0.07, 0.00005, 2, "wide")

			// モーションを出力する
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

			mlog.I("Complete!")
		}
	} else {
		heelMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_heel")
		if err != nil {
			mlog.E("Failed to get heel vmd file paths: %v", err)
			return
		}

		var allHeelMotions []*vmd.VmdMotion
		if heelMotionPaths != nil {
			// 腕IK ------------
			mlog.I("Read Heel Motion ================")
			allHeelMotions, err = utils.ReadVmdFiles(heelMotionPaths)
			if err != nil {
				mlog.E("Failed to read heel motion: %v", err)
				return
			}

			mlog.I("Convert Arm Ik Motion ================")
			allArmIkMotions := usecase.ConvertArmIk(allHeelMotions, modelPath)

			utils.WriteVmdMotions(allFrames, allArmIkMotions, dirPath, "full", "Full")

			return
		} else {
			groundMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_ground")
			if err != nil {
				mlog.E("Failed to get ground vmd file paths: %v", err)
				return
			}

			var allGroundMotions []*vmd.VmdMotion
			if groundMotionPaths != nil {
				// 足接地 -----------
				mlog.I("Read Ground Motion ================")
				allGroundMotions, err = utils.ReadVmdFiles(groundMotionPaths)
				if err != nil {
					mlog.E("Failed to read ground motion: %v", err)
					return
				}

				mlog.I("Fix Heel Motion ================")
				allHeelMotions := usecase.FixHeel(allFrames, allGroundMotions, modelPath)

				utils.WriteVmdMotions(allFrames, allHeelMotions, dirPath, "5_heel", "Heel")

				return
			} else {

				legIkMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_leg_ik")
				if err != nil {
					mlog.E("Failed to get leg ik vmd file paths: %v", err)
					return
				}

				var allLegIkMotions []*vmd.VmdMotion
				if legIkMotionPaths != nil {
					// 接地 ------------
					mlog.I("Read Leg Ik Motion ================")
					allLegIkMotions, err = utils.ReadVmdFiles(legIkMotionPaths)
					if err != nil {
						mlog.E("Failed to read leg ik motion: %v", err)
						return
					}
					mlog.I("Fix Ground Motion ================")
					allGroundMotions := usecase.FixGround(allLegIkMotions, modelPath)

					utils.WriteVmdMotions(allFrames, allGroundMotions, dirPath, "4_ground", "Ground")

					return
				} else {
					rotateMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_rotate")
					if err != nil {
						mlog.E("Failed to get rotate vmd file paths: %v", err)
						return
					}

					var allRotateMotions []*vmd.VmdMotion
					if rotateMotionPaths != nil {
						// 足IK ------------
						mlog.I("Read Rotate Motion ================")
						allRotateMotions, err = utils.ReadVmdFiles(rotateMotionPaths)
						if err != nil {
							mlog.E("Failed to read rotate motion: %v", err)
							return
						}

						mlog.I("Convert Leg Ik Motion ================")
						allLegIkMotions := usecase.ConvertLegIk(allRotateMotions, modelPath)

						utils.WriteVmdMotions(allFrames, allLegIkMotions, dirPath, "3_leg_ik", "Leg Ik")

						return

					} else {
						moveMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_move")
						if err != nil {
							mlog.E("Failed to get move vmd file paths: %v", err)
							return
						}

						var allMoveMotions []*vmd.VmdMotion
						if moveMotionPaths != nil {
							// 回転 ------------
							mlog.I("Read Move Motion ================")
							allMoveMotions, err = utils.ReadVmdFiles(moveMotionPaths)
							if err != nil {
								mlog.E("Failed to read move motion: %v", err)
								return
							}

							mlog.I("Rotate Motion ================")
							allRotateMotions := usecase.Rotate(allMoveMotions, modelPath)

							utils.WriteVmdMotions(allFrames, allRotateMotions, dirPath, "2_rotate", "Rotate")

							return
						} else {
							// 移動 ------------
							mlog.I("Move Motion ================")
							allMoveMotions := usecase.Move(allFrames)

							// モーションを出力する
							utils.WriteVmdMotions(allFrames, allMoveMotions, dirPath, "1_move", "Move")
							return
						}
					}
				}
			}
		}
	}
}
