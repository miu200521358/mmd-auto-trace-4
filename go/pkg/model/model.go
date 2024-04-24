package model

type Position struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
	Z float64 `json:"z"`
}

type Joint3D struct {
	Joint map[string]Position `json:"3d_joints"`
}

type GlobalJoint3D struct {
	Joint map[string]Position `json:"global_3d_joints"`
}

type Joint2D struct {
	Joint map[string]Position `json:"2d_joints"`
}

type Frame struct {
	TrackedBBox   []float64     `json:"tracked_bbox"`
	Confidential  float64       `json:"conf"`
	Camera        []float64     `json:"camera"`
	Joint3D       Joint3D       `json:"3d_joints"`
	GlobalJoint3D GlobalJoint3D `json:"global_3d_joints"`
	Joint2D       Joint2D       `json:"2d_joints"`
}

type Frames struct {
	Frames map[string]Frame
}

type JointName string

const (
	OPNose        JointName = "OP Nose"           // 0
	OPNeck        JointName = "OP Neck"           // 1
	OPRShoulder   JointName = "OP RShoulder"      // 2
	OPRElbow      JointName = "OP RElbow"         // 3
	OPRWrist      JointName = "OP RWrist"         // 4
	OPLShoulder   JointName = "OP LShoulder"      // 5
	OPElbow       JointName = "OP LElbow"         // 6
	OPLWrist      JointName = "OP LWrist"         // 7
	OPMidHip      JointName = "OP MidHip"         // 8
	OPRHip        JointName = "OP RHip"           // 9
	OPRKnee       JointName = "OP RKnee"          // 10
	OPRAnkle      JointName = "OP RAnkle"         // 11
	OPLHip        JointName = "OP LHip"           // 12
	OPLKnee       JointName = "OP LKnee"          // 13
	OPLAnkle      JointName = "OP LAnkle"         // 14
	OPREye        JointName = "OP REye"           // 15
	OPLEye        JointName = "OP LEye"           // 16
	OPREar        JointName = "OP REar"           // 17
	OPLEar        JointName = "OP LEar"           // 18
	OPLBigToe     JointName = "OP LBigToe"        // 19
	OPLSmallToe   JointName = "OP LSmallToe"      // 20
	OPLHeel       JointName = "OP LHeel"          // 21
	OPRBigToe     JointName = "OP RBigToe"        // 22
	OPRSmallToe   JointName = "OP RSmallToe"      // 23
	OPRHeel       JointName = "OP RHeel"          // 24
	RightAnkle    JointName = "Right Ankle"       // 25
	RightKnee     JointName = "Right Knee"        // 26
	RightHip      JointName = "Right Hip"         // 27
	LeftHip       JointName = "Left Hip"          // 28
	LeftKnee      JointName = "Left Knee"         // 29
	LeftAnkle     JointName = "Left Ankle"        // 30
	RightWrist    JointName = "Right Wrist"       // 31
	RightElbow    JointName = "Right Elbow"       // 32
	RightShoulder JointName = "Right Shoulder"    // 33
	LeftShoulder  JointName = "Left Shoulder"     // 34
	LeftElbow     JointName = "Left Elbow"        // 35
	LeftWrist     JointName = "Left Wrist"        // 36
	NeckLSP       JointName = "Neck (LSP)"        // 37
	TopOfHeadLSP  JointName = "Top of Head (LSP)" // 38
	PelvisMPII    JointName = "Pelvis (MPII)"     // 39
	ThoraxMPII    JointName = "Thorax (MPII)"     // 40
	SpineH36M     JointName = "Spine (H36M)"      // 41
	JawH36M       JointName = "Jaw (H36M)"        // 42
	HeadH36M      JointName = "Head (H36M)"       // 43
	Nose          JointName = "Nose"              // 44
	LeftEye       JointName = "Left Eye"          // 45
	RightEye      JointName = "Right Eye"         // 46
	LeftEar       JointName = "Left Ear"          // 47
	RightEar      JointName = "Right Ear"         // 48
)
