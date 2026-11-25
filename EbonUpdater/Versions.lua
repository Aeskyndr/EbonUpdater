local _, EU = ...
local function version(s)
    if type(s) ~= "string" then return end
    local a,b,c = s:match("^(%d+)%.(%d+)%.(%d+)$")
    if not a or #a > 6 or #b > 6 or #c > 6 then return end
    if tostring(tonumber(a)) ~= a or tostring(tonumber(b)) ~= b or tostring(tonumber(c)) ~= c then return end
    return tonumber(a), tonumber(b), tonumber(c)
end
EU.version = version
function EU.newer(remote, installed)
    local a,b,c = version(remote)
    local x,y,z = version(installed)
    if not a or not x then return nil end
    if a ~= x then return a > x end
    if b ~= y then return b > y end
    return c > z
end
function EU.repo(s)
    if type(s) ~= "string" then return end
    local owner, repo = s:match("^([%w][%w%-]*)/([%w_%.%-]+)$")
    if not owner or owner:lower() == "owner" or repo == "." or repo == ".." then return end
    return s
end
function EU.parse(date, msg)
    if type(date) ~= "string" or not date:match("^%d%d%d%d%-%d%d%-%d%d$") then return end
    if type(msg) ~= "string" or #msg > 16384 or msg:sub(1,12) ~= "EBONUPDATER1" then return end
    if msg:sub(13,13) ~= ";" then return end
    local rest = msg:sub(14)
    if rest == "" or rest:sub(-1) == ";" or rest:find(";;",1,true) then return end
    local entries = {}
    for item in rest:gmatch("[^;]+") do
        local name, repo, v = item:match("^([%w_%-]+)=([^=,]+),([^=,]+)$")
        if not name or #name > 80 or not EU.repo(repo) or not version(v) or entries[name:lower()] then return end
        entries[name:lower()] = {repo=repo:lower(), version=v}
    end
    return entries
end
