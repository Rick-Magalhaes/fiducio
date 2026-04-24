from app.models.xp.xp_model import ProcuracaoXP
from app.models.instrucao.instrucao_btg import InstrucaoVoto
from app.models.instrucao.instrucao_alfm import InstrucaoALFM
from app.models.santander.procuracao_santander import ProcuracaoSantander
from app.models.itau.procuracao_itau import ProcuracaoItau


MODELOS = {
    "XP":          ProcuracaoXP,
    "BTG":          ProcuracaoXP,
    "BTG Instrução 1":     InstrucaoVoto,
    "BTG Instrução 2":   InstrucaoALFM,
    "Santander":   ProcuracaoSantander,
    "Itaú":        ProcuracaoItau,
}
 