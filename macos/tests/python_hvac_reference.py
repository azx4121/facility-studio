"""python-hvac is a reference adapter, not a third independent property source."""
import json
from hvac import Quantity
from hvac.fluids import HumidAir
from CoolProp.HumidAirProp import HAPropsSI

checks=[]
for t,rh,p in [(25,.5,101325),(35,.7,101325),(5,.4,80000)]:
    state=HumidAir(Tdb=Quantity(t,'degC'),RH=Quantity(rh,'frac'),P=Quantity(p,'Pa'))
    h=state.h.to('J/kg').magnitude
    ref=HAPropsSI('H','T',t+273.15,'R',rh,'P',p)
    assert abs(h-ref)<=1e-6
    checks.append({'temperature_c':t,'rh':rh,'pressure_pa':p,'passed':True})
print(json.dumps({'checks':checks,'independent_from_coolprop':False}))
