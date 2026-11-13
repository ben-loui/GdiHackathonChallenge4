import pytest
from behoerden_resolver.supplements import gemfa_assignments


def test_only_explicit_unique_whole_municipalities_without_address_conflicts():
    xml=b'''<GemfaExport xmlns="http://www.itzbund.de/GEMFA/Export/01">
    <FinanzamtListe>
      <Finanzamt FinanzbehoerdeId="F1" Name="TEST ONE"><GemeindeListe><Gemeinde GemeindeRef="G1"/><Gemeinde GemeindeRef="G2"/><Gemeinde GemeindeRef="G3"/></GemeindeListe></Finanzamt>
      <Finanzamt FinanzbehoerdeId="F2" Name="TEST TWO"><GemeindeListe><Gemeinde GemeindeRef="G3"/></GemeindeListe></Finanzamt>
    </FinanzamtListe>
    <BundeslandListe><Bundesland><GemeindeListe>
      <Gemeinde GemeindeId="G1" AGS="01001000" PLZ="10000"/>
      <Gemeinde GemeindeId="G2" AGS="01002000" PLZ="20000"><OrtListe><Ort PLZ="20001"/></OrtListe></Gemeinde>
      <Gemeinde GemeindeId="G3" AGS="01003000" PLZ="30000"/>
      <Gemeinde GemeindeId="G4" AGS="01004000" PLZ="40000"/>
    </GemeindeListe></Bundesland></BundeslandListe>
    <AdressezustaendigkeitListe><Adressezustaendigkeit FinanzamtRef="F2" PLZ="20001" Strasse="TEST STREET" HausNrVon="1"/></AdressezustaendigkeitListe>
    </GemfaExport>'''
    towns,offices,safe,excluded=gemfa_assignments(xml)
    assert safe=={'01001000':'F1'}
    assert excluded['01002000']=='contradicting_address_exception'
    assert excluded['01003000']=='missing_or_multiple_municipality_assignment'
    assert excluded['01004000']=='missing_or_multiple_municipality_assignment'
    with pytest.raises(ValueError,match='Schema'):gemfa_assignments(b'<wrong/>')
