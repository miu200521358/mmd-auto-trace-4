package model

type Position struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
	Z float64 `json:"z"`
}

type PositionVisibility struct {
	X          float64 `json:"x"`
	Y          float64 `json:"y"`
	Z          float64 `json:"z"`
	Visibility float64 `json:"visibility"`
	Presence   float64 `json:"presence"`
}

type Frame struct {
	TrackedBBox   []float64                     `json:"tracked_bbox"`
	Confidential  float64                       `json:"conf"`
	Camera        Position                      `json:"camera"`
	Joint3D       map[string]Position           `json:"3d_joints"`
	GlobalJoint3D map[string]Position           `json:"global_3d_joints"`
	Joint2D       map[string]Position           `json:"2d_joints"`
	Mediapipe     map[string]PositionVisibility `json:"mediapipe"`
}

type Frames struct {
	Path   string
	Frames map[int]Frame `json:"frames"`
}
