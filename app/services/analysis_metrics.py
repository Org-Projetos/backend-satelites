"""
Extrai métricas estruturadas/numéricas da resposta de texto do GPT-4o Vision.
"""

from app.models.schedules_schemas import AnalysisMetricsResponse


def extract_metrics_from_analysis(analysis_text: str) -> AnalysisMetricsResponse:
    """
    Parse a resposta de texto da IA e extrai dados estruturados/numéricos.
    
    Args:
        analysis_text: Texto da análise retornado pelo GPT-4o Vision
    
    Returns:
        AnalysisMetricsResponse com dados estruturados
    """
    
    # Normalizar texto
    text_lower = analysis_text.lower()
    
    # 1. Determinar health_status e health_score
    health_status, health_score = _extract_health_status(text_lower, analysis_text)
    
    # 2. Extrair % de cobertura vegetal
    vegetation_coverage = _extract_vegetation_coverage(text_lower, analysis_text)
    
    # 3. Extrair % de áreas com problemas
    problem_areas = _extract_problem_areas(text_lower, analysis_text)
    
    # 4. Determinar trend e magnitude
    trend, magnitude = _extract_trend(text_lower, analysis_text)
    
    # 5. Extrair key findings
    key_findings = _extract_key_findings(analysis_text)
    
    # 6. Extrair recomendações
    recommendations = _extract_recommendations(analysis_text)
    
    return AnalysisMetricsResponse(
        health_status=health_status,
        health_score=health_score,
        vegetation_coverage_percent=vegetation_coverage,
        problem_areas_percent=problem_areas,
        trend=trend,
        trend_magnitude=magnitude,
        key_findings=key_findings,
        recommendations=recommendations,
    )


def _extract_health_status(text_lower: str, original_text: str) -> tuple[str, float]:
    """Determina status de saúde e score (0-100)."""
    
    # Verificar keywords de criticidade
    if any(word in text_lower for word in ["crítico", "crítica", "severo", "grave", "perda significativa", "desmatamento"]):
        return "crítico", 30.0
    
    if any(word in text_lower for word in ["atenção", "problema", "alerta", "variação", "mudança negativa", "possível"]):
        return "atenção", 60.0
    
    if any(word in text_lower for word in ["saudável", "estável", "consistente", "boa cobertura", "crescimento", "recuperação", "melhorou"]):
        return "saudável", 85.0
    
    # Default: estável/saudável
    return "saudável", 75.0


def _extract_vegetation_coverage(text_lower: str, original_text: str) -> float:
    """Extrai % de cobertura vegetal."""
    
    import re
    
    # Padrões: "X%", "X por cento", "X%"
    patterns = [
        r'(\d+)\s*%',
        r'(\d+)\s*por\s*cento',
    ]
    
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, text_lower)
        matches.extend([int(m) for m in found])
    
    if matches:
        # Pega a mediana dos valores encontrados
        matches.sort()
        return float(matches[len(matches) // 2])
    
    # Se menciona "boa cobertura", estima 75%
    if any(word in text_lower for word in ["boa cobertura", "cobertura verde", "predominância de tons verdes"]):
        return 75.0
    
    # Se menciona "crítico" ou "desmatamento", estima baixo
    if any(word in text_lower for word in ["crítico", "desmatamento", "severamente", "perda significativa"]):
        return 30.0
    
    # Default: estável/normal
    return 60.0


def _extract_problem_areas(text_lower: str, original_text: str) -> float:
    """Extrai % de áreas com problemas."""
    
    import re
    
    # Procura por menções de "problemas", "áreas com problemas", "desmatamento"
    if any(word in text_lower for word in ["áreas com problemas", "desmatamento", "áreas afetadas", "problemas"]):
        # Tenta encontrar % associados
        patterns = [
            r'(?:área|problema|desmate).*?(\d+)\s*%',
            r'(\d+)\s*%.*?(?:problema|área|desmate)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return float(match.group(1))
        
        # Se não encontra %, estima
        if "algumas áreas" in text_lower or "pequenas variações" in text_lower:
            return 15.0
        if "áreas significativas" in text_lower:
            return 35.0
        
        # Default quando há menção de problemas mas sem % específico
        return 20.0
    
    # Se há menção de crítico/severo, assume 40% de problemas
    if any(word in text_lower for word in ["crítico", "severo", "grave", "perda significativa"]):
        return 40.0
    
    # Default: sem problemas detectados
    return 5.0


def _extract_trend(text_lower: str, original_text: str) -> tuple[str, float]:
    """Determina trend (progredindo/regredindo/estável) e magnitude."""
    
    # Progressão
    if any(word in text_lower for word in ["crescimento", "recuperação", "aumento", "melhor", "melhorou", "progredindo", "progrediu"]):
        # Magnitude positiva
        if "significativo" in text_lower or "considerável" in text_lower:
            return "progredindo", 30.0
        if "pequeno" in text_lower or "leve" in text_lower:
            return "progredindo", 10.0
        return "progredindo", 20.0
    
    # Regressão
    if any(word in text_lower for word in ["perda", "redução", "diminuição", "piorou", "piora", "regredindo", "desmatamento"]):
        # Magnitude negativa
        if "significativa" in text_lower or "considerável" in text_lower:
            return "regredindo", -30.0
        if "pequena" in text_lower or "leve" in text_lower:
            return "regredindo", -10.0
        return "regredindo", -20.0
    
    # Estável (default)
    if any(word in text_lower for word in ["estável", "relativamente", "consistente", "mantém"]):
        return "estável", 0.0
    
    return "estável", 0.0


def _extract_key_findings(original_text: str) -> list[str]:
    """Extrai os achados principais do texto."""
    
    findings = []
    lines = original_text.split('\n')
    
    in_findings_section = False
    for line in lines:
        line = line.strip()
        
        # Detecta seções com achados
        if any(keyword in line.lower() for keyword in ["mudanças", "progressão", "regressão", "problemas", "áreas com"]):
            in_findings_section = True
        
        # Coleta bullet points
        if line.startswith('-') or line.startswith('•'):
            finding = line.lstrip('-•').strip()
            if finding and len(finding) > 10:  # Evita linhas muito curtas
                findings.append(finding)
        elif in_findings_section and line and not any(c in line for c in ['#', '**']):
            if len(line) > 15:
                findings.append(line)
    
    return findings[:5]  # Retorna os primeiros 5


def _extract_recommendations(original_text: str) -> list[str]:
    """Extrai recomendações do texto."""
    
    recommendations = []
    lines = original_text.split('\n')
    
    in_recommendations_section = False
    for line in lines:
        line = line.strip()
        
        # Detecta seções com recomendações
        if any(keyword in line.lower() for keyword in ["recomend", "importante monit", "é importante", "sugestão"]):
            in_recommendations_section = True
        
        # Coleta recomendações
        if line.startswith('-') or line.startswith('•'):
            rec = line.lstrip('-•').strip()
            if rec and len(rec) > 10:
                recommendations.append(rec)
        elif in_recommendations_section and line and not any(c in line for c in ['#', '**']):
            if len(line) > 15 and not line.endswith(':'):
                recommendations.append(line)
    
    # Se não encontrou, cria padrões baseado na análise
    if not recommendations:
        text_lower = original_text.lower()
        
        if "monitorar" in text_lower or "acompanhar" in text_lower:
            recommendations.append("Continuar monitorando as áreas identificadas regularmente")
        
        if "problema" in text_lower or "crítico" in text_lower:
            recommendations.append("Investigar as áreas problemáticas para diagnóstico mais detalhado")
        
        if "dinâmica" in text_lower:
            recommendations.append("Acompanhar as dinâmicas locais para entender melhor as mudanças")
        
        if not recommendations:
            recommendations.append("Manter vigilância nas próximas análises para detectar mudanças")
    
    return recommendations[:3]  # Retorna até 3 recomendações
