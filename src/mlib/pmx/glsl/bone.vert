#version 440 core

in layout(location = 0) vec3  position;
in layout(location = 1) float indexPer;
in layout(location = 2) float selected;

// ボーン変形行列を格納するテクスチャ
uniform sampler2D boneMatrixTexture;
uniform int boneMatrixWidth;
uniform int boneMatrixHeight;

uniform mat4 modelViewProjectionMatrix;
uniform int boneCount;

uniform vec4 selectBoneColor;
uniform vec4 unselectBoneColor;

out vec4 boneColor;

void main() {
    vec4 position4 = vec4(position, 1.0);
    int boneIndex = int(indexPer * boneCount);

    // テクスチャからボーン変形行列を取得する
    int rowIndex = boneIndex * 4 / boneMatrixWidth;
    int colIndex = (boneIndex * 4) - (boneMatrixWidth * rowIndex);

    // 各頂点で使用されるボーン変形行列を計算する
    mat4 transformMatrix = mat4(0.0);
    {
        vec4 row0 = texelFetch(boneMatrixTexture, ivec2(colIndex + 0, rowIndex), 0);
        vec4 row1 = texelFetch(boneMatrixTexture, ivec2(colIndex + 1, rowIndex), 0);
        vec4 row2 = texelFetch(boneMatrixTexture, ivec2(colIndex + 2, rowIndex), 0);
        vec4 row3 = texelFetch(boneMatrixTexture, ivec2(colIndex + 3, rowIndex), 0);
        transformMatrix = mat4(row0, row1, row2, row3);
    }
    gl_Position = modelViewProjectionMatrix * transformMatrix * position4;

    // ボーンが選択されている場合、選択色
    boneColor = mix(unselectBoneColor, selectBoneColor, selected);
}