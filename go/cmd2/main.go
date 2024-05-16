package main

import (
	"flag"
	"fmt"
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

	armIkMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_arm_ik")
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
			{
				for i, motion := range narrowReduceMotions {
					mlog.I("Output Narrow Reduce Motion [%d/%d] ...", i, len(narrowReduceMotions))

					motionName := fmt.Sprintf("%02d_8_reduce_narrow.vmd", i+1)
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

					motionName := fmt.Sprintf("%02d_9_reduce_wide.vmd", i+1)
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

			prevArmIkMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_arm_ik-process")
			if err != nil {
				mlog.E("Failed to get arm vmd file paths: %v", err)
				return
			}

			var prevArmIkMotions []*vmd.VmdMotion
			if prevArmIkMotionPaths != nil {
				// 腕IK(途中VMD) ------------
				mlog.I("Read Arm Ik Process Motion ================")
				prevArmIkMotions, err = utils.ReadVmdFiles(prevArmIkMotionPaths)
				if err != nil {
					mlog.E("Failed to read arm ik process motion: %v", err)
					return
				}
			}

			mlog.I("Convert Arm Ik Motion ================")
			allArmIkMotions := usecase.ConvertArmIk(allHeelMotions, prevArmIkMotions, modelPath, 100000)

			{
				for i, motion := range allArmIkMotions {
					mlog.I("Output Full Motion [%d/%d] ...", i, len(allArmIkMotions))

					motionName := fmt.Sprintf("%02d_7_arm_ik.vmd", i+1)
					motion.Path = filepath.Join(dirPath, motionName)
					err := vmd.Write(motion)
					if err != nil {
						mlog.E("Failed to write full vmd: %v", err)
					}
				}
			}

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

				{
					for i, motion := range allHeelMotions {
						mlog.I("Output Heel Motion [%d/%d] ...", i, len(allHeelMotions))

						motionName := fmt.Sprintf("%02d_6_heel.vmd", i+1)
						motion.Path = filepath.Join(dirPath, motionName)
						err := vmd.Write(motion)
						if err != nil {
							mlog.E("Failed to write heel vmd: %v", err)
						}
					}
				}

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

					{
						for i, motion := range allGroundMotions {
							mlog.I("Output Ground Motion [%d/%d] ...", i, len(allGroundMotions))

							motionName := fmt.Sprintf("%02d_5_ground.vmd", i+1)
							motion.Path = filepath.Join(dirPath, motionName)
							err := vmd.Write(motion)
							if err != nil {
								mlog.E("Failed to write ground vmd: %v", err)
							}
						}
					}

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

						prevLegIkMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_leg_ik-process")
						if err != nil {
							mlog.E("Failed to get leg ik process vmd file paths: %v", err)
							return
						}

						var prevLegIkMotions []*vmd.VmdMotion
						if prevLegIkMotionPaths != nil {
							// 足IK(途中VMD) ------------
							mlog.I("Read Leg Ik Process Motion ================")
							prevLegIkMotions, err = utils.ReadVmdFiles(prevLegIkMotionPaths)
							if err != nil {
								mlog.E("Failed to read leg ik process motion: %v", err)
								return
							}
						}

						mlog.I("Convert Leg Ik Motion ================")
						allLegIkMotions := usecase.ConvertLegIk(allRotateMotions, prevLegIkMotions, modelPath, 100000)

						{
							for i, motion := range allLegIkMotions {
								mlog.I("Output Leg IK Motion [%d/%d] ...", i, len(allLegIkMotions))

								motionName := fmt.Sprintf("%02d_4_leg_ik.vmd", i+1)
								motion.Path = filepath.Join(dirPath, motionName)
								err := vmd.Write(motion)
								if err != nil {
									mlog.E("Failed to write leg ik vmd: %v", err)
								}
							}
						}

						return

					} else {
						moveMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_move")
						if err != nil {
							mlog.E("Failed to get move vmd file paths: %v", err)
							return
						}

						moveMpMotionPaths, err := utils.GetVmdFilePaths(dirPath, "_mp-move")
						if err != nil {
							mlog.E("Failed to get move vmd file paths: %v", err)
							return
						}

						var allMoveMotions, allMpMoveMotions []*vmd.VmdMotion
						if moveMotionPaths != nil && moveMpMotionPaths != nil {
							// 回転 ------------
							mlog.I("Read Move Motion ================")
							allMoveMotions, err = utils.ReadVmdFiles(moveMotionPaths)
							if err != nil {
								mlog.E("Failed to read move motion: %v", err)
								return
							}

							mlog.I("Read Move Mp Motion ================")
							allMpMoveMotions, err = utils.ReadVmdFiles(moveMpMotionPaths)
							if err != nil {
								mlog.E("Failed to read move mp motion: %v", err)
								return
							}

							mlog.I("Rotate Motion ================")
							allRotateMotions := usecase.Rotate(allFrames, allMoveMotions, allMpMoveMotions, modelPath)

							{
								for i, motion := range allRotateMotions {
									mlog.I("Output Rotate Motion [%d/%d] ...", i, len(allRotateMotions))

									motionName := fmt.Sprintf("%02d_3_rotate.vmd", i+1)
									motion.Path = filepath.Join(dirPath, motionName)
									err := vmd.Write(motion)
									if err != nil {
										mlog.E("Failed to write rotate vmd: %v", err)
									}
								}
							}

							return
						} else {
							// 移動 ------------
							mlog.I("Move Motion ================")
							allMoveMotions, allMpMoveMotions := usecase.Move(allFrames)

							// モーションを出力する
							{
								for i, motion := range allMoveMotions {
									mlog.I("Output Move Motion [%d/%d] ...", i, len(allMoveMotions))

									motionName := fmt.Sprintf("%02d_1_move.vmd", i+1)
									motion.Path = filepath.Join(dirPath, motionName)
									err := vmd.Write(motion)
									if err != nil {
										mlog.E("Failed to write move vmd: %v", err)
									}
								}
							}
							{
								for i, motion := range allMpMoveMotions {
									mlog.I("Output mediapipe Move Motion [%d/%d] ...", i, len(allMpMoveMotions))

									motionName := fmt.Sprintf("%02d_2_mp-move.vmd", i+1)
									motion.Path = filepath.Join(dirPath, motionName)
									err := vmd.Write(motion)
									if err != nil {
										mlog.E("Failed to write mp-move vmd: %v", err)
									}
								}
							}

							return
						}
					}
				}
			}
		}
	}
}
