"""Build an offline RR scouting dashboard from the supplied ZIP."""
import argparse
import base64
import json
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parent
METHOD = [
 ("Coverage and eligibility", "Primary pool: IPL and T20I. Exclude emerging-team T20s, super overs, matches flagged with revised innings or target (revision timing is unknown), and incomplete first innings before inferring a chase target. Minimum 60 pressure balls, 60 ordinary balls, and 8 pressure matches with at least 3 balls per match."),
 ("Before the delivery", "Reconstruct the score, wickets and legal balls used before every event. An uninterrupted chase target is the completed first-innings total plus one. Wides, Overstep and the one-run 'other' extras are treated as illegal deliveries; the latter is an assumption. Penalty events do not consume a ball. Include byes in team totals and exclude them from bowler charges. Charge the primary no-ball extra to the bowler; treat secondary extras as byes."),
 ("First innings", "Compare the pre-ball score with the mean at the start of the same over and wickets-lost band (0-2, 3-5, 6+) in previous dates' first innings in that competition type. Add a within-over allowance at 8 runs per over. Fall back to 8 runs per over when fewer than 5 earlier innings qualify. Batting pressure begins at over 5 when trailing par by 8 runs or more, or with 5 wickets down before over 16. Bowling pressure begins at over 7 when the batting side leads par by 8 or more with at least 4 wickets in hand."),
 ("Chases", "Batting pressure begins at over 7 with required rate 10-18, or 8-18 with at most 4 wickets in hand. Bowling pressure begins with 36 or fewer balls remaining, required rate 5-11 and at least 3 wickets in hand. The upper limits omit very remote chases. These rules approximate competitive pressure and do not estimate win probability."),
 ("Rating", "Batting impact = batter runs minus 12 per striker dismissal, per ball faced. Bowling impact = 12 per bowler-credited wicket minus charged runs, per legal ball. The wicket value is a modelling choice. Within competition, innings and phase, subtract pooled peer impact. Estimate each player's ordinary baseline in each context with 30 balls of shrinkage toward peers. Average that baseline over the player's pressure-ball context mix. Subtract it from pressure impact to obtain lift."),
 ("Ranking and uncertainty", "Shrink pressure impact and lift toward zero with 60 balls. Within each discipline, combine percentiles of peer-adjusted pressure impact (50%), personal lift (30%) and share of qualifying pressure matches above personal baseline (20%). Break ties by pressure balls then player ID. The 90% interval for lift resamples whole pressure matches 300 times, conditional on the fitted baselines. It excludes uncertainty in the estimated baseline and ranking weights."),
 ("Reading the evidence", "Compare full-sample ranks with IPL-only, a tighter pressure rule (+2 runs first-innings margin, narrower chase rate windows), and leave-one-season-out ranks. Context adjustment covers phase, innings and competition type. Venue, opponent quality and changing team roles can still affect results. Roles describe observed usage. Auction availability and retention status are unverified.")
]
def load(path):
    with zipfile.ZipFile(path) as z:
        def csv(name):
            return pd.read_csv(z.open('Data Pack/'+name+'.csv'),low_memory=False)
        d,m,c=csv('ball_by_ball'),csv('matches'),csv('competitions')
    m=m.merge(c,on='comp_id',validate='many_to_one')
    audit={'Indexed matches':len(m),'Matches with deliveries':int(d.match_id.nunique()),'Delivery records':len(d)}
    d=d.merge(m,on='match_id',validate='many_to_one')
    d['comp']=np.select([d.comp_name.str.startswith('IPL '),d.match_format.eq('T20I')],['IPL','T20I'],'Other')
    rinku=d[d.comp.eq('IPL') & d.innings.isin([1,2]) & d.striker_name.eq('Rinku Singh') & ~d.extras_type.isin(['wide','Overstep','other','Penalty'])]
    phase_check=rinku.groupby(rinku.overid.ge(16)).runs.agg(['sum','size'])
    check=' / '.join(f"{int(row['sum'])} runs from {int(row['size'])} included legal balls" for _,row in phase_check.iterrows())
    audit['Rinku IPL check, overs 1-15 / 16-20']=check
    def keep(mask,label):
        nonlocal d
        audit[label]=int((~mask).sum())
        d=d.loc[mask].copy()
    keep(d.comp.ne('Other'),'Other competition rows excluded')
    keep(d.innings.isin([1,2]),'Super-over rows excluded')
    keep(d[['revised_target','first_inn_revised_overs','second_inn_revised_overs']].isna().all(axis=1),'Revised-match rows excluded')
    # Preserve source event order within overs, including illegal deliveries.
    d=d.sort_values(['match_id','innings','overid'],kind='stable')
    d['legal']=(~d.extras_type.isin(['wide','Overstep','other','Penalty'])).astype(int)
    d['faced']=(~d.extras_type.isin(['wide','Penalty'])).astype(int)
    d['total']=d.runs+d.extras1_runs+d.extras_2_runs
    d['charged']=d.runs+d.extras1_runs.where(d.extras_type.isin(['wide','Overstep','other']),0)
    d['bw']=d.dismissal_type.isin(['Caught','Bowled','LBW','Stump','Hit Wicket']).astype(int)
    d['out']=(d.is_wicket & d.dismissed_player_id.eq(d.striker_id)).astype(int)
    d['wk']=d.is_wicket.astype(int)
    groups=d.groupby(['match_id','innings'])
    for source,name in [('legal','used'),('wk','lost'),('total','score')]:
        d[name]=groups[source].cumsum()-d[source]
    first=d[d.innings.eq(1)].groupby('match_id').agg({'legal':'sum','wk':'sum','total':'sum'})
    complete=first[(first.legal>=120)|(first.wk>=10)]
    d['need']=d.match_id.map(complete.total)+1-d.score
    keep(d.innings.eq(1)|d.need.notna(),'Chase rows without complete opening innings')
    d['left']=120-d.used
    keep(d.left.gt(0)&d.lost.lt(10)&(d.innings.eq(1)|d.need.gt(0)),'Inconsistent pre-ball states excluded')
    d['phase']=np.select([d.overid<=6,d.overid<=15],['Powerplay','Middle'],'Death')
    d['year']=d.match_date.str[:4]
    d['band']=np.select([d.lost<=2,d.lost<=5],[0,1],2)
    keys=['comp','overid','band']
    opening=d[d.innings.eq(1)].drop_duplicates(['match_id','overid'])
    dates=d[keys+['match_date']].drop_duplicates()
    totals=opening.groupby(keys+['match_date']).score.agg(['sum','count']).reset_index()
    dates=dates.merge(totals,how='left').fillna(0).sort_values('match_date')
    prior=dates.groupby(keys)[['sum','count']].cumsum()-dates[['sum','count']]
    dates['par']=(prior['sum']/prior['count'].clip(lower=1)).where(prior['count']>=5,(dates.overid-1)*8)
    d=d.merge(dates[keys+['match_date','par']],validate='many_to_one')
    d['margin']=d.score-d.par-(d.used%6)*8/6
    d['rrr']=6*d.need/d.left
    audit['Analysed rows']=len(d)
    audit['Analysed matches']=int(d.match_id.nunique())
    audit['Ambiguous other extras retained']=int(d.extras_type.eq('other').sum())
    return d,audit

def summarize(d,role,strict=False):
    bat=role=='Batters'
    s=int(strict)
    first=d.innings.eq(1)
    if bat:
        p=(first&(d.overid>=5)&((d.margin<=-8-2*s)|((d.lost>=5)&(d.overid<=15))))|(~first&(d.overid>=7)&(d.rrr<=18-s)&((d.rrr>=10+s)|((d.lost>=6)&(d.rrr>=8+s))))
        pid,name,ball,runs,wk='striker_id','striker_name','faced','runs','out'
    else:
        p=(first&(d.overid>=7)&(d.margin>=8+2*s)&(d.lost<=6))|(~first&(d.left<=36)&d.rrr.between(5+s,11-s)&(d.lost<=7))
        pid,name,ball,runs,wk='bowler_id','bowler_name','legal','charged','bw'
    cols=[pid,name,'comp','year','phase','innings','match_id',ball,runs,wk]
    a=d[cols].copy()
    a.columns=['id','name','comp','year','phase','innings','match','balls','runs','wk']
    a['pressure']=p.astype(int)
    a['impact']=(a.runs-12*a.wk)*(1 if bat else -1)
    return a.groupby(['id','name','comp','year','phase','innings','match','pressure'],as_index=False)[['balls','runs','wk','impact']].sum(),p

def rate(a,ci=False):
    ctx=['comp','phase','innings']
    sums=['balls','runs','wk','impact']
    ordinary=a[a.pressure.eq(0)]
    peers=ordinary.groupby(ctx)[sums].sum()
    peers['peer']=peers.impact/peers.balls.clip(lower=1)
    own=ordinary.groupby(['id']+ctx)[sums].sum().rename(columns={'balls':'ob','impact':'oi'})
    p=a[a.pressure.eq(1)].join(peers.peer,on=ctx).join(own[['ob','oi']],on=['id']+ctx).fillna({'ob':0,'oi':0})
    p=p.dropna(subset=['peer']).copy()
    p['above']=p.impact-p.balls*p.peer
    p['lift']=p.impact-p.balls*(p.oi+30*p.peer)/(p.ob+30)
    pm=p.groupby(['id','match'])[['balls','lift']].sum()
    qualifying=pm[pm.balls>=3]
    w=p.groupby('id')[sums+['above','lift']].sum()
    w['matches']=qualifying.groupby('id').size()
    w['win']=qualifying.lift.gt(0).groupby('id').mean()
    w=w[(w.balls>=60)&(w.matches>=8)&(ordinary.groupby('id').balls.sum().reindex(w.index).fillna(0)>=60)].copy()
    if w.empty:return []
    w['adj']=w.above/(w.balls+60)
    w['gain']=w.lift/(w.balls+60)
    w['rating']=100*(.5*w.adj.rank(pct=True)+.3*w.gain.rank(pct=True)+.2*w.win.rank(pct=True))
    w=w.reset_index().sort_values(['rating','balls','id'],ascending=[False,False,True])
    names=a.drop_duplicates('id').set_index('id').name
    phases=p.groupby(['id','phase']).balls.sum().unstack(fill_value=0).idxmax(axis=1)
    out=[]
    for rank,row in enumerate(w.itertuples(),1):
        rec=dict(id=int(row.id),name=names[row.id],rank=rank,rating=round(row.rating,2),balls=int(row.balls),runs=int(row.runs),wk=int(row.wk),matches=int(row.matches),win=round(100*row.win,1),lift=round(100*row.lift/row.balls,2),phase=phases[row.id])
        if ci:
            g=pm.loc[row.id]
            ix=np.random.default_rng(int(row.id)).integers(0,len(g),(300,len(g)))
            den=g.balls.to_numpy()[ix].sum(axis=1)
            est=100*g.lift.to_numpy()[ix].sum(axis=1)/np.maximum(1,den)
            rec['ci']=np.round(np.quantile(est,[.05,.95]),1).tolist()
            rec['history']=[[int(idx),int(v.balls),round(100*v.lift/v.balls,1)] for idx,v in g.iterrows() if v.balls>=3]
        out.append(rec)
    return out

def report(data,path):
    styles=getSampleStyleSheet()
    story=[]
    def title(t): story.extend([Paragraph(t,styles['Title']),Spacer(1,10)])
    def para(t): story.extend([Paragraph(t,styles['BodyText']),Spacer(1,6)])
    title('Rajasthan Royals | Pressure scouting')
    para('IPL 2027 auction research / SupeRR Selector Season 2')
    for k,v in METHOD[:4]:
        story.append(Paragraph(k,styles['Heading2']))
        para(v)
    para('Coverage audit: '+', '.join(f'{k}: {v:,}' if isinstance(v,int) else f'{k}: {v}' for k,v in data['audit'].items())+'.')
    story.append(PageBreak())
    title('Rating and validation')
    for k,v in METHOD[4:]:
        story.append(Paragraph(k,styles['Heading2']))
        para(v)
    for role,example in data['examples'].items():
        para(f'<b>{role}</b> / {example}')
    for role,rows in data['roles'].items():
        story.append(PageBreak())
        title(role+' under pressure')
        para('Ordered submission shortlist. Lift is the difference from a context-matched personal baseline in wicket-adjusted runs per 100 balls. Phase identifies the largest pressure sample.')
        grid=[['#','Player','Score','Balls','Matches','Above %','Lift','Phase']]
        for r in rows[:10]:
            grid.append([r['rank'],r['name'],f"{r['rating']:.2f}",r['balls'],r['matches'],r['win'],r['lift'],r['phase']])
        table=Table(grid,repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#152746')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#faeff2')]),('FONTSIZE',(0,0),(-1,-1),8)]))
        story.extend([table,Spacer(1,12)])
        for r in rows[:10]:
            action='batting' if role=='Batters' else 'bowling'
            para(f"<b>{r['name']}</b> / Assess for {r['phase'].lower()}-overs {action}. Conditional 90% lift interval {r['ci'][0]:+.1f} to {r['ci'][1]:+.1f}. IPL-only rank: {r['ipl'] or 'insufficient evidence'}.")
    SimpleDocTemplate(str(path),pagesize=A4,leftMargin=40,rightMargin=40,topMargin=40,bottomMargin=35).build(story)

def build(path):
    out=ROOT/'dist'
    out.mkdir(exist_ok=True)
    d,audit=load(path)
    matches=d.drop_duplicates('match_id').set_index('match_id')
    data=dict(audit=audit,method=METHOD,roles={},segments={},examples={},matches={int(i):[r.match_date,r.home_team,r.away_team] for i,r in matches.iterrows()})
    for role in ['Batters','Bowlers']:
        a,flag=summarize(d,role)
        ranks=rate(a,True)
        scenarios={'ipl':a[a.comp.eq('IPL')],'strict':summarize(d,role,True)[0]}
        scenarios.update({f'omit{year}':a[a.year.ne(year)] for year in sorted(a.year.unique())})
        for key,frame in scenarios.items():
            ordering={r['id']:r['rank'] for r in rate(frame)}
            for r in ranks:r[key]=ordering.get(r['id'])
        data['roles'][role]=ranks
        ids=[r['id'] for r in ranks]
        g=a[a.id.isin(ids)].groupby(['id','comp','year','phase','innings','pressure'])[['balls','runs','wk']].sum().reset_index()
        data['segments'][role]=g.values.tolist()
        bat=role=='Batters'
        col='striker_id' if bat else 'bowler_id'
        sample=d[flag & d[col].isin(ids)].drop_duplicates([col,'match_id']).set_index([col,'match_id'])
        for player in ranks:
            for obs in player['history']:
                event=sample.loc[(player['id'],obs[0])]
                situation=f"{event.score}/{event.lost}, {event.left} balls left"
                if event.innings==2:situation+=f", {int(event.need)} to win"
                obs.append(situation)
        ex=d[flag & d.innings.eq(2) & d[col].eq(ids[0]) & d.legal.eq(1)].iloc[0]
        impact=ex.runs-12*ex.out if bat else 12*ex.bw-ex.charged
        data['examples'][role]=f"{ranks[0]['name']}, {ex.home_team} v {ex.away_team}, {ex.match_date}, match {ex.match_id}. Before the ball: {int(ex.need)} needed from {ex.left}, {10-ex.lost} wickets in hand (required rate {ex.rrr:.1f}). This meets the chase rule. The delivery contributes {impact:+.0f} wicket-adjusted runs before baseline adjustment."
        pd.DataFrame(ranks[:10])[['rank','name','rating','balls','matches','win','lift','phase']].to_csv(out/(role.lower()+'.csv'),index=False)
    report(data,out/'methodology.pdf')
    data['pdf']=base64.b64encode((out/'methodology.pdf').read_bytes()).decode()
    html=(ROOT/'template.html').read_text().replace('/*STYLE*/',(ROOT/'style.css').read_text()).replace('/*APP*/',(ROOT/'app.js').read_text())
    (out/'dashboard.html').write_text(html.replace('/*DATA*/',json.dumps(data,separators=(',',':'),allow_nan=False).replace('<','\\u003c')),encoding='utf8')
    print(audit)
    for role,r in data['roles'].items():print(role,len(r),[x['name'] for x in r[:3]])
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('zip',type=Path)
    build(parser.parse_args().zip)
