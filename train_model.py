from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

def main():
    # Synthetic demo data only; replace with approved historical data for real evaluation.
    rng = np.random.default_rng(42)
    n = 1200
    x = pd.DataFrame({
        "math_marks": rng.uniform(20, 100, n),
        "science_marks": rng.uniform(20, 100, n),
        "english_marks": rng.uniform(20, 100, n),
        "attendance": rng.uniform(35, 100, n),
        "study_hours": rng.uniform(0, 8, n),
        "previous_score": rng.uniform(20, 100, n),
    })
    noise = rng.normal(0, 5, n)
    y = np.clip(.24*x.math_marks + .24*x.science_marks + .18*x.english_marks
                + .12*x.attendance + 2.2*x.study_hours + .16*x.previous_score
                + noise - 12, 0, 100)
    xt, xv, yt, yv = train_test_split(x, y, test_size=.2, random_state=42)
    model = RandomForestRegressor(n_estimators=180, random_state=42, min_samples_leaf=3)
    model.fit(xt, yt)
    pred = model.predict(xv)
    out = Path(__file__).parent / "models" / "performance_model.joblib"
    out.parent.mkdir(exist_ok=True)
    joblib.dump(model, out)
    print("Model saved:", out)
    print(f"Demo MAE: {mean_absolute_error(yv, pred):.2f}; demo R2: {r2_score(yv, pred):.3f}")
    print("These metrics use synthetic data and do not prove real-world accuracy.")

if __name__ == "__main__":
    main()
