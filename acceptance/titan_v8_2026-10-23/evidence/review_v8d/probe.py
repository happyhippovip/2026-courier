import sys, random, time
sys.path.insert(0, "/tmp/claude-0/-home-user-2026-courier/4510bb24-32c0-5203-8ebf-43dd2db70f44/scratchpad/guardwt")
from courier_core.provider_cli_guard import provider_in_script as S, _segments
cases = {
 "sh \\\" escape miss": 'echo "x\\"" ; codex',
 "sh \\\" FP": 'echo "a\\"; codex"',
 "sh bare \\\" miss": 'echo \\"; codex',
 "ps `\" in dq miss": 'Write-Host "x`""; codex',
 "ps `\" FP": 'Write-Host "a`"; codex"',
 "ps bare `\" miss": 'Write-Host `"; codex',
 "ps `n bare": 'Write-Host line`nnext; Get-Date',
 "ps `n dq": 'Write-Host "line`nnext"; codex',
 "ps line-continuation": 'Get-ChildItem `\n  -Recurse; codex',
 "ps two escapes": 'Write-Host a`tb; codex c`td',
 "cmd ^\" miss": 'echo ^" & codex',
 "cmd ^& FP": 'echo a ^& codex',
 "herestring odd quote miss": '$x = @"\nsay "hi\n"@\ncodex',
 "herestring sq miss": "$x = @'\nit's\n'@\ncodex",
 "herestring even": '$x = @"\nsay "hi"\n"@\ncodex',
 "$( with quoted paren miss": 'x=$(echo ")"); codex',
 "sh if": 'if codex; then :; fi',
 "sh then": 'if true; then codex; fi',
 "sh do": 'for i in 1; do codex; done',
 "sh !": '! codex',
 "sh while": 'while codex; do :; done',
 "cmd for do": 'for %i in (a) do codex',
 "cmd if exist": 'if exist x codex',
 "ps if": 'if ($a) { codex }',
 "ps &": "& 'C:\\Program Files\\codex\\codex.exe' exec",
 "nested $()": 'echo "$(echo $(codex))"',
 "sq in dq": '''echo "it's"; codex''',
 "dq in sq": """echo 'say "hi'; codex""",
 "ps dq dbl": 'Write-Host "a""b"; codex',
}
for k,v in cases.items():
    print(f"{k:28} -> {S(v)!r}")
# depth clobber
for n in (5,7,20,200,900,2000,10000):
    t="$("*n+"codex"+")"*n
    try: r=S(t)
    except Exception as e: r=type(e).__name__
    print("balanced $( x",n,r)
    t="$("*n+"codex"
    try: r=S(t)
    except Exception as e: r=type(e).__name__
    print("unbal $( x",n,r)
    t="echo $(true) "+"`"*0+"$(true)"*n
for n in (7,50):
    t="`$(`"*n
    try: r=S(t)
    except Exception as e: r=type(e).__name__
    print("mix",n,r)
# fuzz
random.seed(1)
alpha=list("'\"`$()\\{}|&;@ \n\r\t\x00^é漢") + ["$(", "codex", "@\"", "\"@", "``"]
errs=0; worst=0
for it in range(20000):
    s="".join(random.choice(alpha) for _ in range(random.randint(0,200)))
    t0=time.perf_counter()
    try: S(s)
    except Exception as e:
        errs+=1
        if errs<4: print("EXC",type(e).__name__, repr(s[:80]))
    worst=max(worst,time.perf_counter()-t0)
print("fuzz errs",errs,"worst",worst)
for name,s in [("big $(",("$(" * 20000)), ("big `", "`a"*30000), ("big quote","\"a"*30000), ("big mix","$( ` \" ' ) "*5000)]:
    s=s[:65536]
    t0=time.perf_counter()
    try: r=S(s)
    except Exception as e: r=type(e).__name__
    print(name, r, round(time.perf_counter()-t0,3))
