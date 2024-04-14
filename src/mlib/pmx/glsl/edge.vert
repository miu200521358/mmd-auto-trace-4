#version 440 core

in layout(location = %d) vec3  position;
in layout(location = %d) vec3  normal;
in layout(location = %d) vec2  uv;
in layout(location = %d) vec2  extendUv;
in layout(location = %d) float vertexEdge;
in layout(location = %d) vec4  boneIndexes;
in layout(location = %d) vec4  boneWeights;
in layout(location = %d) vec3  morphPos;
in layout(location = %d) vec4  morphUv;
in layout(location = %d) vec4  morphUv1;
in layout(location = %d) vec3  morphAfterPos;

// ボーン変形行列を格納するテクスチャ
uniform sampler2D boneMatrixTexture;
uniform int boneMatrixWidth;
uniform int boneMatrixHeight;

uniform vec3 lightPos;
uniform vec3 cameraPos;
uniform mat4 modelViewMatrix;
uniform mat4 modelViewProjectionMatrix;

uniform float edgeSize;

void main() {

    // 各頂点で使用されるボーン変形行列を計算する
    mat4 boneTransformMatrix = mat4(0.0);
    for(int i = 0; i < 4; i++) {
        float boneWeight = boneWeights[i];
        if (boneWeight <= 0.0) {
            continue;
        }
        int boneIndex = int(boneIndexes[i]);

        // テクスチャからボーン変形行列を取得する
        int rowIndex = boneIndex * 4 / boneMatrixWidth;
        int colIndex = (boneIndex * 4) - (boneMatrixWidth * rowIndex);

        vec4 row0 = texelFetch(boneMatrixTexture, ivec2(colIndex + 0, rowIndex), 0);
        vec4 row1 = texelFetch(boneMatrixTexture, ivec2(colIndex + 1, rowIndex), 0);
        vec4 row2 = texelFetch(boneMatrixTexture, ivec2(colIndex + 2, rowIndex), 0);
        vec4 row3 = texelFetch(boneMatrixTexture, ivec2(colIndex + 3, rowIndex), 0);
        mat4 boneMatrix = mat4(row0, row1, row2, row3);

        // ボーン変形行列を乗算する
        boneTransformMatrix += boneMatrix * boneWeight;
    }

    // エッジサイズｘ頂点エッジ倍率ｘモーフ倍率＋モーフバイアス
    float edgeWight = edgeSize * vertexEdge;

    // ボーン変形後頂点モーフ変形量
    mat4 afterVertexTransformMatrix = mat4(1.0);
    afterVertexTransformMatrix[3] = vec4(morphAfterPos, 1.0); // 4列目に移動量を設定

    // 頂点位置
    gl_Position = modelViewProjectionMatrix * afterVertexTransformMatrix * boneTransformMatrix * (vec4(position + morphPos + (normal * edgeWight * 0.02), 1.0));
}
