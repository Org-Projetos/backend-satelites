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


class AnalysisScheduler:
    """Agendador de análises recorrentes."""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.schedule_repo = get_schedule_repository()
        self.history_repo = get_history_repository()

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

    def _run_weekly_analyses_for_schedule(self, schedule):
        """
        Versão síncrona para rodar análise de um schedule.
        Ideal para chamar de threads que não têm event loop.
        """
        print(f"\n📊 Iniciando análise para schedule {schedule.id}")
        try:
            asyncio.run(self._process_schedule(schedule))
            print(f"✅ Análise concluída para {schedule.id}\n")
        except Exception as e:
            print(f"❌ Erro ao processar {schedule.id}: {e}\n")
            import traceback
            traceback.print_exc()

    async def _process_schedule(self, schedule):
        """
        Processa uma análise agendada (comparação temporal de 2 imagens).
        
        Fluxo:
        1. Busca a imagem mais recente (cena_recent)
        2. Busca a imagem anterior mais recente (cena_previous) - continua até achar
        3. Renderiza as 2 imagens (truecolor + NDVI)
        4. Envia para Claude para análise comparativa
        5. Salva resultado (sem armazenar imagens)
        """
        start_time = datetime.utcnow()

        try:
            # 1. Determina data de busca da 1ª imagem (mais recente)
            last_history = self.history_repo.get_latest_by_schedule(schedule.id)
            if last_history and last_history.scene_recent:
                # Se já tem histórico, busca imagens após a última cena_recent
                search_date_recent = (datetime.fromisoformat(last_history.scene_recent.date.replace('Z', '+00:00')).date() + timedelta(days=1)).strftime("%Y-%m-%d")
                print(f"     📅 Última cena_recent: {last_history.scene_recent.date}")
                print(f"     🔍 Buscando nova cena_recent a partir de {search_date_recent}")
            else:
                # Primeira execução: busca próximo a hoje
                search_date_recent = datetime.utcnow().strftime("%Y-%m-%d")
                print(f"     📅 Primeira execução! Buscando cena_recent próxima a {search_date_recent}")

            # 1a. Busca cena_recent (mais recente)
            print(f"     🔍 Buscando cena_recent...")
            print(f"        BBox: {schedule.bbox}")
            print(f"        Data: {search_date_recent}")
            print(f"        Max Cloud Cover: {schedule.max_cloud_cover}%")
            
            scene_recent = await image_selector.select_best_scene(
                bbox=schedule.bbox,
                date=search_date_recent,
                max_cloud_cover=schedule.max_cloud_cover,
            )

            if not scene_recent:
                print(f"     ❌ Nenhuma cena_recent encontrada!")
                raise ValueError("Nenhuma cena disponível para a data")
            
            print(f"     ✅ Cena_recent selecionada: {scene_recent.id}")
            print(f"        Data: {scene_recent.date}")
            print(f"        Cloud Cover: {scene_recent.cloudCover}%")

            # 1b. Busca cena_previous (anterior, continua até achar uma válida)
            print(f"     🔍 Buscando cena_previous (anterior)...")
            
            # Começa a buscar 15 dias antes da cena_recent
            scene_recent_date = datetime.fromisoformat(scene_recent.date.replace('Z', '+00:00')).date()
            search_date_previous = (scene_recent_date - timedelta(days=15)).strftime("%Y-%m-%d")
            
            scene_previous = None
            max_search_iterations = 5  # Tenta até 5 vezes em janelas diferentes
            current_iteration = 0
            
            while not scene_previous and current_iteration < max_search_iterations:
                print(f"        Tentativa {current_iteration + 1}: Buscando antes de {search_date_previous}")
                
                scene_previous = await image_selector.select_best_scene(
                    bbox=schedule.bbox,
                    date=search_date_previous,
                    max_cloud_cover=schedule.max_cloud_cover,
                )
                
                if scene_previous:
                    print(f"        ✅ Cena_previous encontrada: {scene_previous.id}")
                    print(f"           Data: {scene_previous.date}")
                    print(f"           Cloud Cover: {scene_previous.cloudCover}%")
                else:
                    # Volta mais 30 dias
                    search_date_previous = (datetime.fromisoformat(search_date_previous + "T00:00:00Z").date() - timedelta(days=30)).strftime("%Y-%m-%d")
                    current_iteration += 1
            
            if not scene_previous:
                print(f"     ⚠️ Nenhuma cena_previous encontrada! Usando apenas cena_recent.")
            
            # 2. Renderiza as 2 imagens
            print(f"     🎨 Renderizando imagens...")
            
            truecolor_recent_bytes = await process_api.render_optical(
                bbox=schedule.bbox,
                date=scene_recent.date,
                visual_type="truecolor",
                resolution=schedule.resolution,
                max_cloud_cover=schedule.max_cloud_cover,
                satellite_type="sentinel2",
            )
            ndvi_recent_bytes = await process_api.render_optical(
                bbox=schedule.bbox,
                date=scene_recent.date,
                visual_type="ndvi",
                resolution=schedule.resolution,
                max_cloud_cover=schedule.max_cloud_cover,
                satellite_type="sentinel2",
            )
            print(f"        ✅ Cena_recent renderizada (Truecolor: {len(truecolor_recent_bytes)} bytes, NDVI: {len(ndvi_recent_bytes)} bytes)")
            
            truecolor_previous_bytes = None
            ndvi_previous_bytes = None
            if scene_previous:
                truecolor_previous_bytes = await process_api.render_optical(
                    bbox=schedule.bbox,
                    date=scene_previous.date,
                    visual_type="truecolor",
                    resolution=schedule.resolution,
                    max_cloud_cover=schedule.max_cloud_cover,
                    satellite_type="sentinel2",
                )
                ndvi_previous_bytes = await process_api.render_optical(
                    bbox=schedule.bbox,
                    date=scene_previous.date,
                    visual_type="ndvi",
                    resolution=schedule.resolution,
                    max_cloud_cover=schedule.max_cloud_cover,
                    satellite_type="sentinel2",
                )
                print(f"        ✅ Cena_previous renderizada (Truecolor: {len(truecolor_previous_bytes)} bytes, NDVI: {len(ndvi_previous_bytes)} bytes)")

            # 3. Envia para IA para análise comparativa
            print(f"     🤖 Analisando com Claude...")
            
            truecolor_recent_b64 = ai_vision.encode_image_to_base64(truecolor_recent_bytes)
            ndvi_recent_b64 = ai_vision.encode_image_to_base64(ndvi_recent_bytes)
            
            truecolor_previous_b64 = None
            ndvi_previous_b64 = None
            if truecolor_previous_bytes and ndvi_previous_bytes:
                truecolor_previous_b64 = ai_vision.encode_image_to_base64(truecolor_previous_bytes)
                ndvi_previous_b64 = ai_vision.encode_image_to_base64(ndvi_previous_bytes)
            
            # Monta prompt com datas das imagens
            analysis_prompt = f"""
Analise as imagens satellite de sensoriamento remoto e compare a situação atual com a anterior:

**Imagem Recente (Data: {scene_recent.date})**
- Truecolor: mostra a cor natural
- NDVI: mostra o índice de vegetação

**Imagem Anterior (Data: {scene_previous.date if scene_previous else 'N/A'})**
- Truecolor: mostra a cor natural
- NDVI: mostra o índice de vegetação

Analise as mudanças e evolução entre as duas datas, focando em:
- Mudanças na cobertura vegetal
- Áreas com problemas
- Progressão ou regressão da vegetação

Responda em português simples, sem diagnósticos específicos.
"""
            
            ai_report = await ai_vision.analyze_with_claude_vision(
                truecolor_b64=truecolor_recent_b64,
                ndvi_b64=ndvi_recent_b64,
                area_hectares=schedule.area_hectares,
                date=scene_recent.date,
                bbox=schedule.bbox,
                custom_prompt=analysis_prompt,
                previous_truecolor_b64=truecolor_previous_b64,
                previous_ndvi_b64=ndvi_previous_b64,
            )

            # 4. Salva no histórico (SÓ A ANÁLISE, SEM IMAGENS)
            processing_time = f"{(datetime.utcnow() - start_time).total_seconds():.2f}s"
            
            self.history_repo.create(
                schedule_id=schedule.id,
                execution_date=datetime.utcnow(),
                scene_recent_id=scene_recent.id,
                scene_recent_date=scene_recent.date,
                scene_recent_cloud_cover=scene_recent.cloudCover,
                scene_recent_satellite_type=scene_recent.satelliteType,
                scene_previous_id=scene_previous.id if scene_previous else None,
                scene_previous_date=scene_previous.date if scene_previous else None,
                scene_previous_cloud_cover=scene_previous.cloudCover if scene_previous else None,
                scene_previous_satellite_type=scene_previous.satelliteType if scene_previous else None,
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
                scene_recent_id=None,
                scene_recent_date=None,
                scene_recent_cloud_cover=None,
                scene_recent_satellite_type=None,
                scene_previous_id=None,
                scene_previous_date=None,
                scene_previous_cloud_cover=None,
                scene_previous_satellite_type=None,
                analysis="",
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
