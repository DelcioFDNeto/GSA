"""Simulador visual de tráfego (gêmeo digital do cruzamento) para demonstração.

O navegador simula os veículos (modelo microscópico) e desenha o cruzamento visto de cima; uma
câmera sintética gera as detecções que o YOLO + ByteTrack produziriam (caixas, classes, ids e
confiança). O servidor deste pacote faz o papel do sistema de detecção: conta os veículos por
zona com `deteccao.zonas`, envia o lote para `POST /cruzamentos/{id}/leituras` com a chave do
sistema de detecção e devolve ao navegador o ciclo calculado pelo motor do GSA, que passa a
comandar os semáforos simulados.

Uso: python -m simulador   (banco de demonstração próprio; ver README)
"""
