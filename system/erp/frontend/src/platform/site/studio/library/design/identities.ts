/** Site-scoped design recipes, not the ERP-wide theme installer. */
export const designIdentities=[
 {id:'builtin.design.ink',name:'Ink & paper',palette:{background:'#FCFAF5',foreground:'#242220',card:'#FFFFFF',primary:'#263F36','primary-foreground':'#FFFFFF'},typography:{family:'serif' as const},radius:8},
 {id:'builtin.design.slate',name:'Clear slate',palette:{background:'#F8FAFC',foreground:'#172033',card:'#FFFFFF',primary:'#334C80','primary-foreground':'#FFFFFF'},typography:{family:'sans-serif' as const},radius:12},
] as const;
