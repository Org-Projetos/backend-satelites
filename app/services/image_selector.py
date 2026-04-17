"""
Serviço para seleção automática da melhor imagem de satélite.
"""

from typing import Optional

from app.models.schemas import Scene
from app.services import stac


async def select_best_scene(
    bbox: list[float],
    date: str,
    max_cloud_cover: float = 20,
) -> Optional[Scene]:
    """
    Seleciona a melhor cena Sentinel-2 para uma data específica com busca progressiva.
    
    Estratégia de busca:
    1. Busca em janela de ±15 dias da data alvo
    2. Se não encontrar, expande para ±30 dias
    3. Se não encontrar, expande para ±60 dias
    4. Filtra por cobertura de nuvens usando cloudCover endpoint
    5. Prioriza a cena mais próxima da data alvo com menor cobertura de nuvens
    
    Args:
        bbox: Coordenadas da área de interesse
        date: Data alvo (YYYY-MM-DD)
        max_cloud_cover: Máxima cobertura de nuvens aceitável (%)
    
    Returns:
        Melhor cena encontrada ou None se nenhuma adequada
    """
    from datetime import datetime, timedelta
    
    # Converte data para datetime
    target_date = datetime.fromisoformat(date)
    
    # Janelas de busca progressivas (em dias)
    search_windows = [15, 30, 60]
    
    for window_days in search_windows:
        print(f"🔍 Tentativa com janela de ±{window_days} dias...")
        
        # Define janela de busca atual
        start_date = (target_date - timedelta(days=window_days)).strftime("%Y-%m-%d")
        end_date = (target_date + timedelta(days=window_days)).strftime("%Y-%m-%d")
        
        try:
            # Busca cenas Sentinel-2 no período
            print(f"🔍 Buscando cenas de {start_date} a {end_date}")
            scenes = await stac.search_scenes(
                bbox=bbox,
                start=start_date,
                end=end_date,
                satellite_type="sentinel2",
                max_cloud_cover=100,  # Busca todas, vamos filtrar manualmente
            )
            
            print(f"📊 Encontradas {len(scenes)} cenas na janela de ±{window_days} dias")
            if not scenes:
                print(f"❌ Nenhuma cena encontrada na janela de ±{window_days} dias")
                continue  # Tenta próxima janela
            
            # Avalia cada cena usando o cloudCover já retornado pelo STAC
            best_scene = None
            best_score = float('inf')
            acceptable_scenes = []

            print(f"🔎 Avaliando {len(scenes)} cenas (cloudCover do STAC)...")
            for i, scene in enumerate(scenes):
                cloud_cover = scene.cloudCover
                print(f"  📸 Cena {i+1}: {scene.id} - {scene.date} - {cloud_cover}% nuvens")

                if cloud_cover > max_cloud_cover:
                    print(f"    ❌ Rejeitada: {cloud_cover}% > {max_cloud_cover}%")
                    continue

                print(f"    ✅ Aceita: {cloud_cover}% ≤ {max_cloud_cover}%")
                acceptable_scenes.append(scene)

                scene_date = datetime.fromisoformat(scene.date.split('T')[0])
                days_diff = abs((scene_date - target_date).days)
                score = days_diff + (cloud_cover * 0.5)
                print(f"    📊 Score: {score} (dias: {days_diff}, nuvens: {cloud_cover}%)")

                if score < best_score:
                    best_score = score
                    best_scene = scene
                    print(f"    🏆 Nova melhor cena!")
            
            if best_scene:
                print(f"� Sucesso! Melhor cena encontrada na janela de ±{window_days} dias:")
                print(f"🏆 {best_scene.id} - {best_scene.cloudCover}% nuvens")
                print(f"📈 Total de cenas aceitáveis: {len(acceptable_scenes)}")
                return best_scene
            else:
                print(f"❌ Nenhuma cena adequada encontrada na janela de ±{window_days} dias")
                # Continua para próxima janela
        
        except Exception as e:
            print(f"❌ Erro na busca com janela de ±{window_days} dias: {e}")
            continue  # Tenta próxima janela
    
    # Se chegou aqui, não encontrou em nenhuma janela
    print(f"💔 Busca finalizada: Nenhuma cena com ≤{max_cloud_cover}% de nuvens encontrada em até ±60 dias")
    return None