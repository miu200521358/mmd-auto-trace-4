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

uniform vec3 cameraPos;
uniform mat4 modelViewMatrix;
uniform mat4 modelViewProjectionMatrix;

uniform vec4 diffuse;
uniform vec3 ambient;
uniform vec4 specular;

uniform int useToon;
uniform int useSphere;
uniform int sphereMode;
uniform vec3 lightDirection;

uniform int isShowBoneWeight;
uniform int showBoneIndexes[50];

out float alpha;
out vec4 vertexColor;
out vec3 vertexSpecular;
out vec2 vertexUv;
out vec3 vetexNormal;
out vec2 sphereUv;
out vec3 eye;
out float totalBoneWeight;

bool containBone(int boneIndex) {
    for (int i = 0; i < 50; i++) {
        if (showBoneIndexes[i] == boneIndex) {
            return true;
        }
    }
    return false;
}

void main() {
    vec4 position4 = vec4(position + morphPos, 1.0);

    // 各頂点で使用されるボーン変形行列を計算する
    totalBoneWeight = 0;
    mat4 boneTransformMatrix = mat4(0.0);
    for(int i = 0; i < 4; i++) {
        float boneWeight = boneWeights[i];
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

        // ボーンウェイトを保持しておく
        if (containBone(boneIndex)) {
            totalBoneWeight += boneWeight;
        }
    }

    // ボーン変形後頂点モーフ変形量
    mat4 afterVertexTransformMatrix = mat4(1.0);
    afterVertexTransformMatrix[3] = vec4(morphAfterPos, 1.0); // 4列目に移動量を設定

    // ボーンがまったく表示対象外でも少し描画するため、下限を決めておく
    totalBoneWeight = clamp(totalBoneWeight, 0.2, 1.0);

    // 各頂点で使用される法線変形行列をボーン変形行列から回転情報のみ抽出して生成する
    mat3 normalTransformMatrix = mat3(boneTransformMatrix);

    // 頂点位置
    gl_Position = modelViewProjectionMatrix * afterVertexTransformMatrix * boneTransformMatrix * position4;

    // 頂点法線
    vetexNormal = normalize(normalTransformMatrix * normalize(normal)).xyz;

    // 材質の透過度
    alpha = diffuse.w;

    // 頂点色設定
    vertexColor = clamp(diffuse, 0.0, 1.0);

    if (0 == useToon) {
        // ディフューズ色＋アンビエント色 計算
        float lightNormal = clamp(dot( vetexNormal, -lightDirection ), 0.0, 1.0);
        vertexColor.rgb += diffuse.rgb * lightNormal;
        vertexColor = clamp(vertexColor, 0.0, 1.0);
    }

    // テクスチャ描画位置
    vertexUv = uv + morphUv.xy;

    if (1 == useSphere) {
        // Sphereマップ計算
        if (3 == sphereMode) {
            // PMXサブテクスチャ座標
            sphereUv = extendUv;
        }
        else {
	        // スフィアマップテクスチャ座標
            vec3 normalWv = mat3(modelViewMatrix) * vetexNormal;
	        sphereUv.x = normalWv.x * 0.5f + 0.5f;
	        sphereUv.y = 1 - (normalWv.y * -0.5f + 0.5f);
        }
        sphereUv += morphUv1.xy;
    }

    // カメラとの相対位置
    vec3 eye = cameraPos - (boneTransformMatrix * position4).xyz;

    // スペキュラ色計算
    vec3 HalfVector = normalize( normalize(eye) + -lightDirection );
    vertexSpecular = pow( max(0, dot( HalfVector, vetexNormal )), max(0.000001, specular.w) ) * specular.rgb;

    vertexColor.rgb = vetexNormal;
}
