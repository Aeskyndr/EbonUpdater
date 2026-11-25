local EU = {}
assert(loadfile('Versions.lua'))('EbonUpdater',EU)
assert(EU.newer('1.10.0','1.9.9'))
assert(not EU.newer('1.0.0','1.0.0'))
assert(not EU.newer('01.0.0','1.0.0'))
assert(not EU.repo('OWNER/EbonUpdater'))
local msg='EBONUPDATER1;EbonUpdater=Example/EbonUpdater,0.1.1;EbonLoot=Example/EbonLoot,1.10.0'
assert(EU.parse('2026-11-24',msg).ebonloot.version=='1.10.0')
assert(not EU.parse('2026-11-24',msg..';'))
assert(not EU.parse('2026-11-24',msg..';EbonLoot=Example/EbonLoot,2.0.0'))
assert(not EU.parse('2026-11-24','some login message'))
local f, output, calls, result = {}, {}, 0, nil
function CreateFrame() return f end
function f:RegisterEvent() end
function f:UnregisterEvent() end
function f:SetScript(key,fn) self[key]=fn end
function GetNumAddOns() return 2 end
function GetAddOnInfo(i) return i==1 and 'EbonUpdater' or 'EbonLoot' end
function GetAddOnMetadata(i,k)
    if k=='Version' then return i==2 and '1.9.9' or '0.1.0' end
    return i==2 and 'Example/EbonLoot' or 'Example/EbonUpdater'
end
function time() return 100000 end
function print(s) output[#output+1]=s end
function FetchLoginMessage(url) assert(url=='https://raw.githubusercontent.com/Example/EbonUpdater/main/versions.json'); calls=calls+1 end
function GetLoginMessageResult() if result then return (unpack or table.unpack)(result) end end
SlashCmdList={}
assert(loadfile('Core.lua'))('EbonUpdater',EU)
f.OnEvent()
assert(calls==0); f:OnUpdate(8); assert(calls==1)
result={'OK','2026-11-24',msg}; f:OnUpdate(0.5)
assert(not f.OnUpdate); assert(EbonUpdaterDB.message==msg); assert(output[#output]:find('2 update'))
SlashCmdList.EBONUPDATER('check'); result={'OK','2026-11-24','ordinary motd'}; f:OnUpdate(0.5)
assert(not f.OnUpdate and EbonUpdaterDB.message==msg)
SlashCmdList.EBONUPDATER('check'); result=nil; f:OnUpdate(15)
assert(not f.OnUpdate and EbonUpdaterDB.message==msg)
SlashCmdList.EBONUPDATER('off'); assert(EbonUpdaterDB.enabled==false)
