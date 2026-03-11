#!/usr/bin/env python3
"""
Script para testar e visualizar as imagens geradas pela API.
"""

import base64
import requests
import json
from datetime import datetime
import os

def save_base64_image(base64_data: str, filename: str):
    """Salva uma imagem base64 como arquivo PNG."""
    image_data = base64.b64decode(base64_data)
    with open(filename, 'wb') as f:
        f.write(image_data)
    print(f"💾 Imagem salva: {filename} ({len(image_data)} bytes)")

def test_api():
    """Testa a API e salva as imagens."""
    
    # Dados de teste
    data = {
        'bbox': [-42.85539059797703, -4.968836726442746, -42.81487851301608, -4.950195690169812],
        'date': '2026-02-09',
        'areaHectares': 100.0,
        'maxCloudCover': 20,
        'resolution': 'medium'
    }
    
    print("🧪 Testando API de análise...")
    print(f"📍 Área: {data['bbox']}")
    print(f"📅 Data: {data['date']}")
    
    try:
        response = requests.post('http://localhost:8000/api/analyze', json=data, timeout=120)
        
        print(f"📡 Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Criar diretório para debug
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_dir = f"debug_images_{timestamp}"
            os.makedirs(debug_dir, exist_ok=True)
            
            # Salvar imagens
            if 'images' in result:
                if 'truecolor' in result['images']:
                    save_base64_image(
                        result['images']['truecolor'], 
                        f"{debug_dir}/truecolor.png"
                    )
                
                if 'ndvi' in result['images']:
                    save_base64_image(
                        result['images']['ndvi'], 
                        f"{debug_dir}/ndvi.png"
                    )
            
            # Mostrar informações
            print(f"\n✅ Análise concluída!")
            print(f"🏆 Cena selecionada: {result['selectedScene']['id']}")
            print(f"📅 Data da cena: {result['selectedScene']['date']}")
            print(f"☁️ Cobertura de nuvens: {result['selectedScene']['cloudCover']:.1f}%")
            print(f"⏱️ Tempo de processamento: {result['metadata']['processingTime']}")
            
            # Salvar análise completa
            with open(f"{debug_dir}/analysis.json", 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            print(f"\n📊 Análise da IA:")
            print(f"{result['analysis'][:300]}...")
            
            print(f"\n📁 Arquivos salvos em: {debug_dir}/")
            
        else:
            print(f"❌ Erro: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")

if __name__ == "__main__":
    test_api()