// Shared mutable state for Rogue and Ultimate card UI/runtime.
// Classic scripts intentionally share these lexical bindings with index.html.

let rogueOfferCards = [];
let ultimateOfferCards = [];

let activeRogueCard = null;
let activeAiRogueCard = null;
let rogueUses = {};
let rogueSealing = false;
let rogueSeals = [];
let aiRogueSeals = [];
let puppetMode = false;
let pendingRogueSealPoints = [];
let rogueSealRequired = 0;
let rogueSealWaitingForOpponent = false;
let quickthinkAwaitingAiMove = false;

let ultimateMode = false;
let ultimatePlayerCard = null;
let ultimateAiCard = null;
let ultimatePlayerName = "";
let ultimateAiName = "";

let cardTurnTimer = null;
let cardTurnTick = null;
let cardTurnDeadline = 0;
let cardTurnRemaining = 0;
let cardTurnLabel = "";
let cardTurnKey = "";
