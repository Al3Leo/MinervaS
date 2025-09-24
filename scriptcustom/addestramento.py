# Carica dataset
df = pd.read_csv("dataset_livelli.csv")

# Scelta feature
X = df[['rtt_medio', 'pdr_percent']]
y = df['livello']

# Gestione dataset
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Normalizzazione
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Crea e addestra modello
knn = KNeighborsClassifier(n_neighbors=1)
knn.fit(X_train_scaled, y_train)
# Salva il modello e lo scaler
joblib.dump(knn, "knn_model.pkl")
joblib.dump(scaler, "scaler.pkl")

# Valutazione del modello
y_pred = knn.predict(X_test_scaled)
print("Classification report:")
print(classification_report(y_test, y_pred))
print("Accuracy:", accuracy_score(y_test, y_pred))
