from app.models.xp.xp_model import ProcuracaoXP
from app.models.instrucao.instrucao_btg import InstrucaoVoto
from app.models.instrucao.instrucao_alfm import InstrucaoALFM
from app.models.instrucao.instrucao_opea import InstrucaoOpea
from app.models.santander.procuracao_santander import ProcuracaoSantander
from app.models.itau.procuracao_itau import ProcuracaoItau
from app.models.safra.procuracao_safra import ProcuracaoSafra

MODELOS = {
    "XP":               ProcuracaoXP,
    "BTG":              ProcuracaoXP,
    "BTG Instrução 1":  InstrucaoVoto,
    "BTG Instrução 2":  InstrucaoALFM,
    "Opea":             InstrucaoOpea,
    "Santander":        ProcuracaoSantander,
    "Itaú":             ProcuracaoItau,
    "Safra":            ProcuracaoSafra,
}