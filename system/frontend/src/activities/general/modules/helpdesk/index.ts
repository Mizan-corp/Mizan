import {lazy} from "react";
import type {ModuleDefinition} from "@app/framework/types";
const definition:ModuleDefinition={id:"helpdesk",activity:"general",kind:"business",status:"active",
 screens:{"helpdesk.catalog":lazy(()=>import("../../../../features/helpdesk/HelpdeskPage"))},widgets:{}};
export default definition;
