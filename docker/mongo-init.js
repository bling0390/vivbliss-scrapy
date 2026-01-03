// Create application user with readWrite on the target database.
// Environment variables are passed by the Mongo container on first startup.
const dbName = process.env.MONGO_DB || "vivbliss";
const appUser = process.env.MONGO_APP_USERNAME || "vivbliss_app";
const appPass = process.env.MONGO_APP_PASSWORD || "vivbliss_secret";

db = db.getSiblingDB(dbName);
db.createUser({
  user: appUser,
  pwd: appPass,
  roles: [{ role: "readWrite", db: dbName }],
});
