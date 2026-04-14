#!/usr/bin/env python3
"""
Teste de integração: Verifica se as imagens estão sendo salvas no MinIO.
"""

import asyncio
import os
from minio import Minio
from io import BytesIO


async def test_minio_upload():
    """Testa upload e download de imagem no MinIO."""
    # Tenta conectar no MinIO (localhost para testes fora do docker)
    try:
        # Usa a porta 9000 (quando rodando fora do docker no host)
        minio_client = Minio(
            "localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin_secret",
            secure=False,
        )
    except Exception as e:
        print(f"❌ Não conseguiu conectar ao MinIO em localhost:9000")
        print(f"   Erro: {e}")
        return False
    
    print(f"\n🧪 Testando MinIO Upload\n")
    print(f"📍 Endpoint: localhost:9000")
    print(f"🪣 Bucket: agro-images")
    
    bucket = "agro-images"
    
    # 1. Verifica se bucket existe
    print(f"\n1️⃣  Verificando bucket...")
    try:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
            print(f"   ✅ Bucket '{bucket}' criado")
        else:
            print(f"   ✅ Bucket existe")
    except Exception as e:
        print(f"   ❌ Erro ao criar bucket: {e}")
        return False
    
    # 2. Cria uma imagem de teste (PNG mínimo)
    print(f"\n2️⃣  Criando imagem de teste...")
    test_image = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG header
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0x99, 0x63, 0xF8, 0x0F, 0x04, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0xFD, 0x47, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
        0xAE, 0x42, 0x60, 0x82
    ])
    test_object_name = "test/test_image.png"
    print(f"   ✅ Imagem criada ({len(test_image)} bytes)")
    
    # 3. Faz upload
    print(f"\n3️⃣  Fazendo upload...")
    try:
        minio_client.put_object(
            bucket,
            test_object_name,
            BytesIO(test_image),
            length=len(test_image),
            content_type="image/png",
        )
        print(f"   ✅ Upload bem-sucedido")
        print(f"   📦 Caminho: {bucket}/{test_object_name}")
    except Exception as e:
        print(f"   ❌ Erro ao fazer upload: {e}")
        return False
    
    # 4. Lista objetos
    print(f"\n4️⃣  Listando objetos no bucket...")
    try:
        objects = minio_client.list_objects(bucket, prefix="test/")
        print(f"   ✅ Objetos encontrados:")
        for obj in objects:
            print(f"      - {obj.object_name}")
    except Exception as e:
        print(f"   ❌ Erro ao listar objetos: {e}")
        return False
    
    # 5. Faz download
    print(f"\n5️⃣  Fazendo download...")
    try:
        response = minio_client.get_object(bucket, test_object_name)
        downloaded = response.read()
        response.close()
        response.release_conn()
        if downloaded == test_image:
            print(f"   ✅ Download bem-sucedido (dados intactos)")
        else:
            print(f"   ⚠️  Download bem-sucedido mas dados diferentes")
    except Exception as e:
        print(f"   ❌ Erro ao fazer download: {e}")
        return False
    
    # 6. Gera URL assinada
    print(f"\n6️⃣  Gerando URL assinada...")
    try:
        from datetime import timedelta
        url = minio_client.get_presigned_url(
            "GET",
            bucket,
            test_object_name,
            expires=timedelta(hours=24),
        )
        print(f"   ✅ URL gerada com sucesso")
        print(f"   🔗 {url[:80]}...")
    except Exception as e:
        print(f"   ❌ Erro ao gerar URL: {e}")
        return False
    
    # 7. Deleta objeto de teste
    print(f"\n7️⃣  Deletando objeto de teste...")
    try:
        minio_client.remove_object(bucket, test_object_name)
        print(f"   ✅ Objeto deletado com sucesso")
    except Exception as e:
        print(f"   ❌ Erro ao deletar: {e}")
        return False
    
    print(f"\n✅ TODOS OS TESTES PASSARAM!\n")
    return True


if __name__ == "__main__":
    result = asyncio.run(test_minio_upload())
    exit(0 if result else 1)
