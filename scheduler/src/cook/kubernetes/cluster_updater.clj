(ns cook.kubernetes.cluster-updater
  (:require [clj-http.client :as http]
            [clj-time.coerce :as c]
            [clj-time.format :as f]
            [clojure.string :as str]
            [cook.config :as config]))

(def gke-create-time-format
  (f/formatter "yyyy-MM-dd'T'HH:mm:ssZ"))

(defn get-cluster-configs-from-gke-catalog
  "Call the GKE Catalog service to get cluster info. Convert that to cook cluster configs."
  []
  (let [{:keys [gke-catalog-url gke-catalog-conn-timeout gke-catalog-socket-timeout]} (config/compute-cluster-options)
        clusters (-> (http/get
                       gke-catalog-url
                       {:as :json
                        :conn-timeout (or gke-catalog-conn-timeout 1000)
                        :socket-timeout (or gke-catalog-socket-timeout 1000)
                        :spnego-auth true})
                   :body
                   :clusters)]
    (->> clusters
         (map (fn [{:keys [cluster google_meta]}]
                (let [{:keys [name state environment]} cluster
                      {:keys [create_time endpoint master_auth]} google_meta]
                  {:name (str name "-" (-> create_time f/parse c/to-epoch))
                   :template (str/lower-case environment)
                   :base-path (str "https://" endpoint)
                   :ca-cert (:cluster_ca_certificate master_auth)
                   :state (case state
                            "OPEN" :running
                            "CORDONED" :draining)
                   :state-locked? false}))))))