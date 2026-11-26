"""Regras de temporização (RF08–RF11).

Cada regra implementa o protocolo `RegraTemporizacao`. Para trocar a regra basta criar uma nova
classe e passá-la ao motor, sem alterar controllers nem o acesso ao banco (RNF09). Todas
distribuem o verde por estágio (vias que abrem juntas) e respeitam mínimo e máximo.
"""

from collections.abc import Sequence
from typing import Protocol

from app.motor.classificacao import FaixasFluxo
from app.motor.estagios import agrupar_estagios, distribuir_verde, montar_resultado
from app.motor.modelos import AjusteAplicado, EntradaVia, ResultadoCalculo


class RegraTemporizacao(Protocol):
    nome: str

    def calcular(
        self, entradas: Sequence[EntradaVia], duracao_ciclo: int, faixas: FaixasFluxo
    ) -> ResultadoCalculo: ...


class DistribuicaoProporcional:
    """Distribui o verde disponível proporcionalmente aos veículos (RF09), garantindo o verde
    mínimo (RF10) e limitando ao máximo (RF11) de cada semáforo.

    Verde disponível = duração do ciclo − soma dos entreverdes (amarelo + vermelho de segurança).
    O peso de cada estágio é a contagem da sua via mais carregada.
    """

    nome = "proporcional_com_limites"

    def calcular(
        self, entradas: Sequence[EntradaVia], duracao_ciclo: int, faixas: FaixasFluxo
    ) -> ResultadoCalculo:
        estagios = agrupar_estagios(entradas)
        verde_disponivel = max(duracao_ciclo - sum(e.entreverde for e in estagios), 0)
        pesos = {e.chave: float(e.veiculos_criticos) for e in estagios}
        verdes, ajustes = distribuir_verde(estagios, pesos, verde_disponivel)
        return montar_resultado(
            self.nome, entradas, estagios, verdes, ajustes, duracao_ciclo, verde_disponivel, faixas
        )


class PlanoFixo:
    """Modo de segurança: divide o verde igualmente entre os estágios, sem usar as contagens.

    Usado quando faltam leituras recentes (câmera ou detector sem enviar dados).
    """

    nome = "plano_fixo"

    def calcular(
        self, entradas: Sequence[EntradaVia], duracao_ciclo: int, faixas: FaixasFluxo
    ) -> ResultadoCalculo:
        estagios = agrupar_estagios(entradas)
        verde_disponivel = max(duracao_ciclo - sum(e.entreverde for e in estagios), 0)
        pesos = {e.chave: 1.0 for e in estagios}
        verdes, ajustes = distribuir_verde(
            estagios, pesos, verde_disponivel, AjusteAplicado.PLANO_FIXO
        )
        return montar_resultado(
            self.nome, entradas, estagios, verdes, ajustes, duracao_ciclo, verde_disponivel, faixas
        )


class Webster:
    """Ciclo ótimo pelo método de Webster, com o verde dividido pelas razões de fluxo.

    - fluxo de cada via q = veículos contados × 3600 / intervalo da contagem (veíc/h);
    - razão de fluxo y = q / (fluxo de saturação por faixa × faixas); a do estágio é a maior;
    - ciclo C = (1,5·L + 5) / (1 − Y), com Y = soma das razões e L = tempo perdido, aproximado
      pela soma dos entreverdes; C fica entre o ciclo mínimo e o máximo configurados;
    - com Y igual ou acima do limite de saturação, usa o ciclo máximo.

    A duração do ciclo passa a acompanhar a demanda: mais curta com pouco trânsito, mais longa
    nos horários de pico.
    """

    nome = "webster"

    def __init__(
        self,
        fluxo_saturacao_por_faixa: float = 1800,
        intervalo_contagem: int = 90,
        ciclo_minimo: int = 40,
        ciclo_maximo: int = 150,
        limite_saturacao: float = 0.9,
    ) -> None:
        if fluxo_saturacao_por_faixa <= 0 or intervalo_contagem <= 0:
            raise ValueError("fluxo de saturação e intervalo de contagem devem ser positivos")
        if not 0 < ciclo_minimo < ciclo_maximo:
            raise ValueError("ciclo mínimo deve ser positivo e menor que o máximo")
        if not 0 < limite_saturacao < 1:
            raise ValueError("limite de saturação deve estar entre 0 e 1")
        self.fluxo_saturacao_por_faixa = fluxo_saturacao_por_faixa
        self.intervalo_contagem = intervalo_contagem
        self.ciclo_minimo = ciclo_minimo
        self.ciclo_maximo = ciclo_maximo
        self.limite_saturacao = limite_saturacao

    def razao_fluxo(self, entrada: EntradaVia) -> float:
        fluxo_hora = entrada.quantidade_veiculos * 3600 / self.intervalo_contagem
        return fluxo_hora / (self.fluxo_saturacao_por_faixa * entrada.quantidade_faixas)

    def calcular(
        self, entradas: Sequence[EntradaVia], duracao_ciclo: int, faixas: FaixasFluxo
    ) -> ResultadoCalculo:
        estagios = agrupar_estagios(entradas)
        razoes = {e.chave: max(self.razao_fluxo(v) for v in e.vias) for e in estagios}
        soma_razoes = sum(razoes.values())
        tempo_perdido = sum(e.entreverde for e in estagios)

        if soma_razoes >= self.limite_saturacao:
            ciclo = self.ciclo_maximo
        elif soma_razoes == 0:
            ciclo = self.ciclo_minimo
        else:
            ciclo = (1.5 * tempo_perdido + 5) / (1 - soma_razoes)
        ciclo = round(min(max(ciclo, self.ciclo_minimo), self.ciclo_maximo))

        verde_disponivel = max(ciclo - tempo_perdido, 0)
        verdes, ajustes = distribuir_verde(estagios, razoes, verde_disponivel)
        return montar_resultado(
            self.nome,
            entradas,
            estagios,
            verdes,
            ajustes,
            ciclo,
            verde_disponivel,
            faixas,
            grau_saturacao=round(soma_razoes, 3),
        )
