"""
Cliente MinIO para armazenamento de imagens de satélite.

Responsável por upload/download de imagens (truecolor, NDVI, etc).
"""

from __future__ import annotations

from io import BytesIO
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.config import get_settings


class MinIOClient:
    """Cliente para interagir com MinIO."""

    def __init__(self):
        settings = get_settings()
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,  # HTTP, não HTTPS (local development)
        )
        self.bucket = settings.minio_bucket

    def ensure_bucket_exists(self) -> None:
        """Cria o bucket se não existir."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                print(f"✅ Bucket '{self.bucket}' criado no MinIO")
        except S3Error as e:
            print(f"❌ Erro ao criar bucket: {e}")
            raise

    def upload_image(self, object_name: str, data: bytes) -> str:
        """
        Faz upload de uma imagem e retorna o caminho/URL do objeto.

        Args:
            object_name: Caminho do objeto no bucket (ex: "schedules/123/truecolor.png")
            data: Bytes da imagem

        Returns:
            Caminho completo do objeto no bucket
        """
        try:
            self.client.put_object(
                self.bucket,
                object_name,
                BytesIO(data),
                length=len(data),
                content_type="image/png",
            )
            return f"{self.bucket}/{object_name}"
        except S3Error as e:
            print(f"❌ Erro ao fazer upload: {e}")
            raise

    def download_image(self, object_name: str) -> bytes:
        """
        Faz download de uma imagem.

        Args:
            object_name: Caminho do objeto no bucket

        Returns:
            Bytes da imagem
        """
        try:
            response = self.client.get_object(self.bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            print(f"❌ Erro ao fazer download: {e}")
            raise

    def get_presigned_url(self, object_name: str, expires_hours: int = 24) -> str:
        """
        Gera uma URL assinada para download da imagem.

        Args:
            object_name: Caminho do objeto
            expires_hours: Tempo de expiração em horas

        Returns:
            URL assinada
        """
        try:
            url = self.client.get_presigned_url(
                "GET",
                self.bucket,
                object_name,
                expires=timedelta(hours=expires_hours),
            )
            return url
        except S3Error as e:
            print(f"❌ Erro ao gerar URL assinada: {e}")
            raise

    def delete_image(self, object_name: str) -> None:
        """Deleta uma imagem."""
        try:
            self.client.remove_object(self.bucket, object_name)
        except S3Error as e:
            print(f"❌ Erro ao deletar imagem: {e}")
            raise

    def list_images(self, prefix: str = "") -> list[str]:
        """Lista todas as imagens com um prefixo."""
        try:
            objects = self.client.list_objects(self.bucket, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            print(f"❌ Erro ao listar imagens: {e}")
            raise


# Singleton global
_minio_client: MinIOClient | None = None


def get_minio_client() -> MinIOClient:
    """Retorna a instância global do cliente MinIO."""
    global _minio_client
    if _minio_client is None:
        _minio_client = MinIOClient()
        _minio_client.ensure_bucket_exists()
    return _minio_client
