"""
Agendador de análises semanais usando APScheduler.

Executa automaticamente análises para todos os agendamentos ativos.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.repositories.schedule_repository import (
    get_schedule_repository,
    get_history_repository,
)
from app.services import process_api, image_selector, ai_vision
from app.services.minio_client import get_minio_client


class AnalysisScheduler:
    """Agendador de análises recorrentes."""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.schedule_repo = get_schedule_repository()
        self.history_repo = get_history_repository()
        self.minio_client = get_minio_client()

    def start(self):
        """Inicia o agendador."""
        # Todo domingo às 00:00 (UTC)
        self.scheduler.add_job(
            self._run_weekly_analyses,
            trigger=CronTrigger(day_of_week=6, hour=0, minute=0),
            id="weekly_analysis_job",
            name="Análises Semanais",
            replace_existing=True,
        )
        self.scheduler.start()
        print("✅ Agendador de análises iniciado!")

    def stop(self):
        """Para o agendador."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("🛑 Agendador de análises parado!")

    def _run_weekly_analyses(self):
        """Executa análises para todos os agendamentos ativos."""
        print(f"\n📊 Iniciando análises semanais em {datetime.utcnow().isoformat()}")

        active_schedules = self.schedule_repo.list_active()
        print(f"   Total de análises ativas: {len(active_schedules)}")

        for schedule in active_schedules:
            try:
                print(f"\n   → Processando: {schedule.id}")
                asyncio.run(self._process_schedule(schedule))
            except Exception as e:
                print(f"   ❌ Erro ao processar {schedule.id}:")
                print(f"      {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()

        print(f"\n✅ Análises semanais concluídas em {datetime.utcnow().isoformat()}\n")

    async def _process_schedule(self, schedule):
        """Processa uma análise agendada."""
        start_time = datetime.utcnow()

        try:
            # 1. Busca última execução para saber a partir de qual data buscar
            last_history = self.history_repo.get_latest_by_schedule(schedule.id)
            if last_history:
                # Busca imagens após a última análise (próximo dia)
                search_date = (last_history.execution_date + timedelta(days=1)).strftime("%Y-%m-%d")
                print(f"     📅 Última análise: {last_history.execution_date}")
                print(f"     🔍 Buscando imagens a partir de {search_date}")
            else:
                # Primeira execução: busca próximo a hoje
                search_date = datetime.utcnow().strftime("%Y-%m-%d")
                print(f"     📅 Primeira execução! Buscando imagens próximas a {search_date}")

            # 2. Seleciona a melhor cena
            print(f"     🔍 Selecionando melhor cena...")
            print(f"        BBox: {schedule.bbox}")
            print(f"        Data: {search_date}")
            print(f"        Max Cloud Cover: {schedule.max_cloud_cover}%")
            
            scene = await image_selector.select_best_scene(
                bbox=schedule.bbox,
                date=search_date,
                max_cloud_cover=schedule.max_cloud_cover,
            )

            if not scene:
                print(f"     ❌ Nenhuma cena encontrada!")
                raise ValueError("Nenhuma cena disponível para a data")
            
            print(f"     ✅ Cena selecionada: {scene.id}")
            print(f"        Data: {scene.date}")
            print(f"        Cloud Cover: {scene.cloudCover}%")
            print(f"        Satélite: {scene.satelliteType}")

            # 3. Renderiza as imagens
            print(f"     🎨 Renderizando imagens...")
            print(f"        Tipo: Truecolor + NDVI")
            print(f"        Resolução: {schedule.resolution}m")
            
            truecolor_bytes = await process_api.render_optical(
                bbox=schedule.bbox,
                date=scene.date,
                visual_type="truecolor",
                resolution=schedule.resolution,
                max_cloud_cover=schedule.max_cloud_cover,
                satellite_type="sentinel2",
            )
            print(f"        ✅ Truecolor: {len(truecolor_bytes)} bytes")

            ndvi_bytes = await process_api.render_optical(
                bbox=schedule.bbox,
                date=scene.date,
                visual_type="ndvi",
                resolution=schedule.resolution,
                max_cloud_cover=schedule.max_cloud_cover,
                satellite_type="sentinel2",
            )
            print(f"        ✅ NDVI: {len(ndvi_bytes)} bytes")

            # 4. Salva no MinIO
            print(f"     💾 Salvando imagens no MinIO...")
            schedule_prefix = f"schedules/{schedule.id}/{scene.date}"
            
            truecolor_path = f"{schedule_prefix}/truecolor.png"
            ndvi_path = f"{schedule_prefix}/ndvi.png"
            
            print(f"     💾 Salvando imagens no MinIO...")
            self.minio_client.upload_image(truecolor_path, truecolor_bytes)
            print(f"        ✅ Upload: {truecolor_path}")
            
            self.minio_client.upload_image(ndvi_path, ndvi_bytes)
            print(f"        ✅ Upload: {ndvi_path}")

            # 5. Gera URLs assinadas
            print(f"     🔗 Gerando URLs assinadas...")
            truecolor_url = self.minio_client.get_presigned_url(truecolor_path)
            print(f"        ✅ Truecolor URL gerada")
            
            ndvi_url = self.minio_client.get_presigned_url(ndvi_path)
            print(f"        ✅ NDVI URL gerada")

            # 6. Envia para IA
            print(f"     🤖 Analisando com GPT-4o Vision...")
            truecolor_b64 = ai_vision.encode_image_to_base64(truecolor_bytes)
            ndvi_b64 = ai_vision.encode_image_to_base64(ndvi_bytes)

            ai_report = await ai_vision.analyze_with_gpt4o_vision(
                truecolor_b64=truecolor_b64,
                ndvi_b64=ndvi_b64,
                area_hectares=schedule.area_hectares,
                date=scene.date,
                bbox=schedule.bbox,
            )

            # 7. Salva no histórico
            processing_time = f"{(datetime.utcnow() - start_time).total_seconds():.2f}s"
            
            self.history_repo.create(
                schedule_id=schedule.id,
                execution_date=datetime.utcnow(),
                scene_id=scene.id,
                scene_date=scene.date,
                scene_cloud_cover=scene.cloudCover,
                scene_satellite_type=scene.satelliteType,
                images={
                    "truecolor": truecolor_url,
                    "ndvi": ndvi_url,
                },
                analysis=ai_report,
                processing_time=processing_time,
                status="success",
            )

            print(f"     ✅ Análise concluída em {processing_time}")

        except Exception as e:
            processing_time = f"{(datetime.utcnow() - start_time).total_seconds():.2f}s"
            
            self.history_repo.create(
                schedule_id=schedule.id,
                execution_date=datetime.utcnow(),
                scene_id=None,
                scene_date=None,
                scene_cloud_cover=None,
                scene_satellite_type=None,
                images={},
                analysis={},
                processing_time=processing_time,
                status="failed",
                error_message=str(e),
            )

            raise


# Singleton global
_scheduler: AnalysisScheduler | None = None


def get_scheduler() -> AnalysisScheduler:
    """Retorna a instância global do agendador."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AnalysisScheduler()
    return _scheduler
