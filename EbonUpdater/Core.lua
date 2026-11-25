local addon, EU = ...
local frame = CreateFrame("Frame")
local INTERVAL, TIMEOUT, LOGIN_DELAY, POLL = 900, 15, 8, 0.5
local db, mode, elapsed, poll, manual, requestedRepo
local function say(s) print("|cffb48cff[EbonUpdater]|r "..s) end
local function log(s)
    if type(EbonholdLog) == "function" then pcall(EbonholdLog, "EbonUpdater: "..s) end
end
local function ownRepo() return EU.repo(GetAddOnMetadata(addon, "X-GitHub")) end
local function installed()
    local list = {}
    for i=1,GetNumAddOns() do
        local name = GetAddOnInfo(i)
        local repo = EU.repo(GetAddOnMetadata(i,"X-GitHub"))
        local v = GetAddOnMetadata(i,"Version")
        if name and repo and EU.version(v) then
            list[#list+1] = {name=name, repo=repo:lower(), version=v}
        end
    end
    table.sort(list,function(a,b) return a.name:lower() < b.name:lower() end)
    return list
end
local function report(entries, details, demo)
    local count, tracked = 0, 0
    for _, a in ipairs(installed()) do
        local remote = entries[a.name:lower()]
        if remote and remote.repo == a.repo then
            tracked = tracked + 1
            if EU.newer(remote.version,a.version) then
                count = count + 1
                say(a.name..": "..a.version.." -> "..remote.version..(demo and " (DEMO)" or ""))
            elseif details then say(a.name..": "..a.version.." ("..(a.version==remote.version and "up to date" or "local version newer")..")") end
        elseif details then say(a.name..": "..a.version.." (not listed or repository mismatch)") end
    end
    if count > 0 then say(count.." update(s) available"..(demo and " (DEMO only)." or ". Run the external helper to install."))
    elseif details then say("No updates among "..tracked.." matched addon(s).") end
end
local function cache()
    if db.source ~= ownRepo() then return end
    return EU.parse(db.date,db.message)
end
local function stop(reason)
    mode=nil; frame:SetScript("OnUpdate",nil)
    if reason then
        log(reason)
        if manual then say(reason.."; cached information was not changed.") end
    end
end
local tick
local function start(force)
    if mode == "request" then if force then say("Check already running.") end; return end
    if mode == "delay" and not force then return end
    manual=force
    local repo=ownRepo()
    if not repo then stop(); if force then say("Set X-GitHub in EbonUpdater.toc, then restart WoW. Try /ebonupdate demo.") end; return end
    if type(FetchLoginMessage)~="function" or type(GetLoginMessageResult)~="function" then stop("Native HTTP API unavailable"); return end
    local now=time()
    if not force and db.source==repo and type(db.checked)=="number" and now>=db.checked and now-db.checked<INTERVAL then
        local entries=cache(); if entries then report(entries,false) end; stop(); return
    end
    -- One attempt per UI session, with a persistent cooldown even on failure.
    if not force and db.attemptSource==repo and type(db.attempt)=="number" and now>=db.attempt and now-db.attempt<INTERVAL then stop(); return end
    db.attempt=now; db.attemptSource=repo
    requestedRepo=repo
    elapsed,poll=0,0; mode="request"
    local ok=pcall(FetchLoginMessage,"https://raw.githubusercontent.com/"..repo.."/main/versions.json")
    if not ok then stop("HTTP request could not start"); return end
    frame:SetScript("OnUpdate",tick)
    if force then say("Checking GitHub...") end
end
tick=function(self,dt)
    elapsed=elapsed+dt
    if mode=="delay" then if elapsed>=LOGIN_DELAY then mode=nil; start(false) end; return end
    if mode~="request" then stop(); return end
    poll=poll+dt
    if poll>=POLL then
        poll=0
        local ok,status,date,msg=pcall(GetLoginMessageResult)
        if not ok then stop("HTTP result unavailable"); return end
        if status then
            local entries=status=="OK" and EU.parse(date,msg)
            if not entries then stop("No valid EbonUpdater manifest (shared HTTP slot, invalid response or network error)"); return end
            local own=entries[addon:lower()]
            if not own or own.repo~=requestedRepo:lower() then stop("Manifest repository mismatch"); return end
            db.source=requestedRepo; db.checked=time(); db.date=date; db.message=msg
            stop(); report(entries,manual); return
        end
    end
    if elapsed>=TIMEOUT then stop("Update check timed out") end
end
frame:RegisterEvent("PLAYER_LOGIN")
frame:SetScript("OnEvent",function()
    if type(EbonUpdaterDB)~="table" then EbonUpdaterDB={} end
    db=EbonUpdaterDB
    frame:UnregisterEvent("PLAYER_LOGIN")
    if db.enabled~=false and ownRepo() then
        mode="delay"; elapsed=0; frame:SetScript("OnUpdate",tick)
    end
end)
SLASH_EBONUPDATER1="/ebonupdate"
SlashCmdList.EBONUPDATER=function(input)
    if not db then return end
    local cmd=(input or ""):match("^%s*(.-)%s*$"):lower()
    if cmd=="check" then start(true)
    elseif cmd=="on" then db.enabled=true; say("Automatic checks enabled.")
    elseif cmd=="off" then db.enabled=false; stop(); say("Automatic checks disabled.")
    elseif cmd=="open" then
        local repo=ownRepo()
        if repo and type(EbonholdOpenURL)=="function" then
            local ok=pcall(EbonholdOpenURL,"https://github.com/"..repo.."/releases")
            if not ok then say("Could not open browser.") end
        else say("Repository or browser API not configured.") end
    elseif cmd=="demo" then
        local v=GetAddOnMetadata(addon,"Version")
        local a,b,c=EU.version(v)
        if a and c<999999 then say(addon..": "..v.." -> "..a.."."..b.."."..(c+1).." (DEMO; no network or update).") end
    elseif cmd=="" then
        say("Automatic checks: "..(db.enabled==false and "off" or "on"))
        if mode then say("Check scheduled or running.") end
        local entries=cache()
        if entries then
            local age=type(db.checked)=="number" and time()-db.checked or INTERVAL
            say("Last successful check: "..(age>=0 and age<INTERVAL and "recent" or "stale cache").."; manifest "..db.date)
            report(entries,true)
        else say("No verified manifest cached.") end
        if not ownRepo() then say("GitHub repository not configured.") end
        say("Commands: check, on, off, open, demo")
    else say("Commands: check, on, off, open, demo") end
end
